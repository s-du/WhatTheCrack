import os
from PySide6.QtGui import *
from PySide6.QtWidgets import *
import widgets as wid
import resources as res
import segment_engine as seg


class CustomDoubleValidator(QDoubleValidator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, string, pos):
        # Replace comma with period for validation
        string = string.replace(',', '.')
        return super().validate(string, pos)

    def fixup(self, string):
        # Replace comma with period in the final string
        return string.replace(',', '.')

class ExclusiveButtonGroup:
    def __init__(self):
        self.buttons = []

    def addButton(self, button):
        self.buttons.append(button)
        # Correctly capture the button reference in the lambda
        button.clicked.connect(lambda checked=False, b=button: self.uncheck_others(b))

    def uncheck_others(self, clicked_button):
        for button in self.buttons:
            if button != clicked_button:
                button.setChecked(False)

class ScaleDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Compute Scale")

        # Create widgets
        self.known_length_edit = QLineEdit()
        self.known_distance_edit = QLineEdit()
        self.result_label = QLabel("Resolution will be shown here")
        self.ok_button = QPushButton("OK")

        # Set input constraints (only numbers)
        float_validator = CustomDoubleValidator()
        float_validator.setNotation(QDoubleValidator.StandardNotation)
        float_validator.setBottom(0)  # Minimum value (e.g., 0 for no negative numbers)
        float_validator.setDecimals(2)
        self.known_length_edit.setValidator(float_validator)
        self.known_distance_edit.setValidator(float_validator)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Known length (in pixels):"))
        layout.addWidget(self.known_length_edit)
        layout.addWidget(QLabel("Known distance (in mm):"))
        layout.addWidget(self.known_distance_edit)
        layout.addWidget(self.ok_button)
        layout.addWidget(self.result_label)
        self.setLayout(layout)

        # Initially disable the OK button
        self.ok_button.setEnabled(False)

        # Connect signals
        self.known_length_edit.textChanged.connect(self.check_inputs)
        self.known_distance_edit.textChanged.connect(self.check_inputs)
        self.ok_button.clicked.connect(self.accept)

    def check_inputs(self):
        # Check if both fields are filled
        if self.known_length_edit.text() and self.known_distance_edit.text():
            try:
                # Attempt to parse the inputs
                known_length = float(self.known_length_edit.text().replace(',', '.'))
                known_distance = float(self.known_distance_edit.text().replace(',', '.'))

                # Check that neither known length nor known distance is zero
                if known_length != 0 and known_distance != 0:
                    self.resolution = known_distance / known_length
                    self.result_label.setText(f"Resolution: {self.resolution} mm/pixel")
                    self.ok_button.setEnabled(True)
                else:
                    self.result_label.setText("Known length and distance cannot be zero")
                    self.ok_button.setEnabled(False)
            except ValueError:
                self.result_label.setText("Invalid input")
                self.ok_button.setEnabled(False)
        else:
            # Disable OK button if either field is empty
            self.ok_button.setEnabled(False)
            self.result_label.setText("Resolution will be shown here")

class CrackApp(QMainWindow):
    def __init__(self, is_dark_theme):
        super().__init__()

        basepath = os.path.dirname(__file__)
        basename = 'crackify'
        uifile = os.path.join(basepath, '%s.ui' % basename)
        wid.loadUi(uifile, self)

        self.setWindowTitle("What the crack!")

        # add actions to action group
        ag = QActionGroup(self)
        ag.setExclusive(True)
        ag.addAction(self.actionMeasure)
        ag.addAction(self.actionHand_selector)

        # mutually exclusive pushbuttons
        self.exclusiveGroup = ExclusiveButtonGroup()
        self.exclusiveGroup.addButton(self.pushButton_show_skel)
        self.exclusiveGroup.addButton(self.pushButton_show_mask)

        self.viewer = wid.PhotoViewer(self)
        self.verticalLayout.addWidget(self.viewer)

        # initial parameters
        self.list_image = ['Original image']
        # self.comboBox.addItems(self.list_image)
        self.active_img = self.list_image[0]
        self.image_loaded = False
        self.resolution = 0

        # connections
        self.actionLoad_image.triggered.connect(self.get_image)
        self.actionSegment.triggered.connect(self.go_segment)
        self.actionSet_scale.triggered.connect(self.set_scale)
        # pushbuttons
        self.pushButton_show_image.clicked.connect(self.update_view)
        self.pushButton_show_skel.clicked.connect(self.update_view)
        self.pushButton_show_mask.clicked.connect(self.update_view)

        if is_dark_theme:
            suf = '_white_tint'
            suf2 = '_white'
        else:
            suf = ''

        self.add_icon(res.find(f'img/camera{suf}.png'), self.actionLoad_image)
        self.add_icon(res.find(f'img/magic{suf}.png'), self.actionSegment)
        self.add_icon(res.find(f'img/hand{suf}.png'), self.actionHand_selector)
        self.add_icon(res.find(f'img/width{suf}.png'), self.actionMeasure)
        self.add_icon(res.find(f'img/ruler{suf}.png'), self.actionSet_scale)
        # push buttons
        self.add_icon(res.find(f'img/photo{suf2}.png'), self.pushButton_show_image)
        self.add_icon(res.find(f'img/skel{suf2}.png'), self.pushButton_show_skel)
        self.add_icon(res.find(f'img/mask{suf2}.png'), self.pushButton_show_mask)

    def set_scale(self):
        dialog = ScaleDialog()
        if dialog.exec_():
            self.resolution = dialog.resolution
            print(f'New resolution is {self.resolution} mm/pixel')
            self.viewer.mm_per_pixel = self.resolution

    def add_icon(self, img_source, pushButton_object):
        """
        Function to add an icon to a pushButton
        """
        pushButton_object.setIcon(QIcon(img_source))

    def update_view(self):
        if self.pushButton_show_image.isChecked():
            if self.pushButton_show_mask.isChecked():
                self.viewer.compose_mask_image(self.output_color_mask)
            elif self.pushButton_show_skel.isChecked():
                self.viewer.compose_mask_image(self.output_skel_color)
            else:
                self.viewer.setPhoto(QPixmap(self.image_path))
        else:
            if self.pushButton_show_mask.isChecked():
                self.viewer.setPhoto(QPixmap(self.output_color_mask))
            elif self.pushButton_show_skel.isChecked():
                self.viewer.setPhoto(QPixmap(self.output_skel_color))
            else:
                # Load the existing image
                original_image = QImage(self.image_path)  # Replace with your image path

                # Create a new white image of the same size
                white_image = QImage(original_image.size(), QImage.Format_ARGB32)
                white_image.fill(Qt.white)  # Fill the image with white color

                # Convert the white QImage to QPixmap
                white_pixmap = QPixmap.fromImage(white_image)
                self.viewer.setPhoto(white_pixmap)


    def go_segment(self):
        # execute YOLO script
        print(self.image_path)
        result = seg.get_segmentation_result(self.image_path)
        self.crack_length, self.output_binary_mask, self.output_color_mask, self.output_skeleton, self.output_skel_color = seg.create_binary_image(result, '')

        self.pushButton_show_mask.setEnabled(True)
        self.pushButton_show_skel.setEnabled(True)
        self.pushButton_show_mask.setChecked(True)

        self.update_view()

    def get_image(self):
        """
        Get the image path from the user
        :return:
        """
        try:
            img = QFileDialog.getOpenFileName(self, u"Ouverture de fichiers", "",
                                                        "Image Files (*.png *.jpg *.bmp *.tif)")
            print(f'the following image will be loaded {img[0]}')
        except:
            pass
        if img[0] != '':
            # load and show new image
            self.load_image(img[0])

    def load_image(self, path):
        """
        Load the new image and reset the model
        :param path:
        :return:
        """
        # self.reset_points()

        self.image_path = path
        self.viewer.setPhoto(QPixmap(path))
        self.viewer.set_base_image(path)
        self.image_loaded = True

        # enable action
        self.actionSegment.setEnabled(True)
        self.actionMeasure.setEnabled(True)
        self.actionSet_scale.setEnabled(True)
        self.actionHand_selector.setEnabled(True)
        self.actionHand_selector.setChecked(True)

        self.pushButton_show_image.setEnabled(True)
        self.pushButton_show_image.setChecked(True)


def main(argv=None):
    """
    Creates the main window for the application and begins the \
    QApplication if necessary.

    :param      argv | [, ...] || None

    :return      error code
    """

    # Define installation path
    install_folder = os.path.dirname(__file__)

    app = None

    # create the application if necessary
    if (not QApplication.instance()):
        app = QApplication(argv)
        app.setStyle('Fusion')

        # test if dark theme is used
        palette = app.palette()
        bg_color = palette.color(QPalette.Window)

        is_dark_theme = bg_color.lightness() < 128
        print(is_dark_theme)

        if is_dark_theme:
            app.setStyleSheet("""
            QPushButton:checked {
                background-color: lightblue;
            }
            """)

    # create the main window

    window = CrackApp(is_dark_theme)
    window.showMaximized()

    # run the application if necessary
    if (app):
        return app.exec_()

    # no errors since we're not running our own event loop
    return 0


if __name__ == '__main__':
    import sys

    sys.exit(main(sys.argv))