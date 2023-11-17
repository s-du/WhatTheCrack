import cv2
import numpy as np
import os
from PIL import Image
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtCore import Signal, QObject
import resources as res
import segment_engine as seg
import sys
import widgets as wid
import re


# parameters
# path (change if necessary)
OUT_BINARY_MASK = 'combined_binary_mask.png'
OUT_COLOR_MASK = 'combined_color_mask.png'
OUT_BINARY_SKELETON = 'skeleton_image.png'
OUT_COLOR_SKELETON = 'skeleton_color.png'


"""
class CustomOutputStream(QObject):
    outputSignal = Signal(str)

    def write(self, text):
        if "step" in text:
            self.outputSignal.emit('read')
        else:
            self.outputSignal.emit(text)

    def flush(self):
        pass

sys.stdout = CustomOutputStream()
"""
class Helper(QObject):
    updateSignal = Signal(str)

    def emit_update(self, value):
        self.updateSignal.emit(value)

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
        ag.addAction(self.actionMeasure_path)
        ag.addAction(self.actionHand_selector)
        ag.addAction(self.actionPaint_mask)
        ag.addAction(self.actionEraser_mask)

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
        self.has_mask = False
        self.resolution = 0
        self.image_w = 0
        self.image_h = 0
        self.crack_length = 0
        self.output_binary_mask = OUT_BINARY_MASK
        self.output_color_mask = OUT_COLOR_MASK
        self.output_skeleton = OUT_BINARY_SKELETON
        self.output_color_skeleton = OUT_COLOR_SKELETON

        # initialize status
        self.update_progress(nb=100, text="Load an image first!")

        # list of line measurements
        self.line_meas_list = []
        self.path_meas_list = []

        # connections
        self.actionLoad_image.triggered.connect(self.get_image)
        self.actionSegment.triggered.connect(self.go_segment)
        self.actionSet_scale.triggered.connect(self.set_scale)
        self.actionMeasure.triggered.connect(self.line_meas)
        self.actionMeasure_path.triggered.connect(self.path_meas)
        self.actionHand_selector.triggered.connect(self.hand_pan)
        self.actionPaint_mask.triggered.connect(self.paint_mask)
        self.actionEraser_mask.triggered.connect(self.erase_mask)

        # pushbuttons
        self.pushButton_show_image.clicked.connect(self.update_view)
        self.pushButton_show_skel.clicked.connect(self.update_view)
        self.pushButton_show_mask.clicked.connect(self.update_view)
        self.pushButton_show_linemeas.clicked.connect(self.toggle_all_meas)
        self.pushButton_export.clicked.connect(self.export_view)
        self.pushButton_export_view.clicked.connect(self.export_current_view)

        # drawing ends
        self.viewer.endDrawing_line_meas.connect(self.get_line_meas)
        self.viewer.endPainting.connect(self.update_image_mask)
        self.viewer.photoClicked.connect(self.get_path)
        self.viewer.pathAdded.connect(self.get_path_measurements)

        # Custom output stream
        # sys.stdout.outputSignal.connect(self.onOutput)

        self.helper = Helper()
        self.helper.updateSignal.connect(self.update_yolo_steps)

        if is_dark_theme:
            suf = '_white_tint'
            suf2 = '_white'
        else:
            suf = ''

        self.add_icon(res.find(f'img/camera{suf}.png'), self.actionLoad_image)
        self.add_icon(res.find(f'img/crack{suf}.png'), self.actionSegment)
        self.add_icon(res.find(f'img/hand{suf}.png'), self.actionHand_selector)
        self.add_icon(res.find(f'img/ruler{suf}.png'), self.actionMeasure)
        self.add_icon(res.find(f'img/magic{suf}.png'), self.actionMeasure_path)
        self.add_icon(res.find(f'img/size{suf}.png'), self.actionSet_scale)
        self.add_icon(res.find(f'img/brush{suf}.png'), self.actionPaint_mask)
        self.add_icon(res.find(f'img/eraser{suf}.png'), self.actionEraser_mask)
        # push buttons
        self.add_icon(res.find(f'img/photo{suf2}.png'), self.pushButton_show_image)
        self.add_icon(res.find(f'img/skel{suf2}.png'), self.pushButton_show_skel)
        self.add_icon(res.find(f'img/mask{suf2}.png'), self.pushButton_show_mask)
        self.add_icon(res.find(f'img/save_as{suf2}.png'), self.pushButton_export)
        self.add_icon(res.find(f'img/view{suf2}.png'), self.pushButton_export_view)
        self.add_icon(res.find(f'img/width{suf2}.png'), self.pushButton_show_linemeas)

    # general functions __________________________________________
    def add_icon(self, img_source, pushButton_object):
        """
        Function to add an icon to a pushButton
        """
        pushButton_object.setIcon(QIcon(img_source))

    def update_progress(self, nb=None, text=''):
        self.label_status.setText(text)
        if nb is not None:
            self.progressBar.setProperty("value", nb)

            # hide progress bar when 100%
            if nb >= 100:
                self.progressBar.setVisible(False)
            elif self.progressBar.isHidden():
                self.progressBar.setVisible(True)

    # paint and erase __________________________________________
    def paint_mask(self):
        self.pushButton_show_mask.setChecked(True)
        self.pushButton_show_skel.setChecked(False)
        self.update_view()

        if self.actionPaint_mask.isChecked():
            # update status
            self.update_progress(text='You can paint on the image. Hold shift and mouse wheel to adapt size')
            # change cursor
            self.viewer.change_to_brush_cursor()
            self.viewer.painting = True
            self.viewer.eraser = False
            self.viewer.point_selection = False

            if self.viewer.hand_drag:
                self.viewer.toggleDragMode()

    def update_image_mask(self, coords):
        if self.has_mask:
            image = Image.open(self.output_binary_mask)
            image_array = np.array(image)

            if not self.viewer.eraser:
                binary_image = seg.create_mask_from_paint(image_array, coords)
            else:
                binary_image = seg.remove_mask_from_paint(image_array, coords)

            self.compute_all_outputs_from_binary(binary_image)

            self.pushButton_show_mask.setEnabled(True)
            self.pushButton_show_skel.setEnabled(True)
            self.pushButton_show_mask.setChecked(True)
            self.actionMeasure_path.setEnabled(True)

            self.update_view()

        else:
            if not self.viewer.eraser:
                image = Image.open(self.image_path)
                width, height = image.size

                # Create an empty black image (binary) of the same dimension
                black_image = np.zeros((height, width), dtype=np.uint8)

                # use painted coordinates to create a new mask
                binary_image = seg.create_mask_from_paint(black_image, coords)

                self.compute_all_outputs_from_binary(binary_image)

                self.pushButton_show_mask.setEnabled(True)
                self.pushButton_show_skel.setEnabled(True)
                self.pushButton_show_mask.setChecked(True)
                self.actionMeasure_path.setEnabled(True)

                self.has_mask = True
                self.update_view()

    def erase_mask(self):
        self.pushButton_show_mask.setChecked(True)
        self.pushButton_show_skel.setChecked(False)
        self.update_view()

        if self.actionEraser_mask.isChecked():
            # update status
            self.update_progress(text='You can remove paint on the image. Hold shift and mouse wheel to adapt size')
            # change cursor
            self.viewer.change_to_brush_cursor()
            self.viewer.painting = True
            self.viewer.eraser = True
            self.viewer.point_selection = False

            if self.viewer.hand_drag:
                self.viewer.toggleDragMode()

    # line measurement __________________________________________
    def toggle_all_meas(self):
        if self.pushButton_show_linemeas.isChecked():
            self.viewer.add_all_line_measurements(self.line_meas_list)
            self.viewer.add_all_path_measurements(self.path_meas_list)
        else:
            self.viewer.clean_scene_line()
            self.viewer.clean_scene_text()
            self.viewer.clean_scene_path()

    def line_meas(self):
        if self.actionMeasure.isChecked():
            self.update_progress(text='Click and drag the measure a distance')
            self.viewer.setCursor(Qt.ArrowCursor)
            # activate drawing tool
            self.point_selection = False
            self.viewer.painting = False

            self.viewer.line_meas = True
            self.viewer.toggleDragMode()

    def get_line_meas(self, line_obj, text_obj):
        self.line_meas_list.append([line_obj, text_obj])

        self.pushButton_show_linemeas.setEnabled(True)
        self.pushButton_show_linemeas.setChecked(True)
        self.hand_pan()

    # path measurement __________________________________________
    def path_meas(self):
        if self.actionMeasure_path.isChecked():
            # update status
            self.update_progress(text='You can click on a crack segment to measure it')
            self.viewer.point_selection = True
            self.viewer.painting = False

            # change cursor
            self.viewer.change_to_brush_cursor()
            if self.viewer.hand_drag:
                self.viewer.toggleDragMode()

    def get_path(self, list):
        x = list[1]
        y = list[0]

        img = cv2.imread(self.output_skeleton)

        close_pixel = seg.find_closest_white_pixel(img[:, :, 1], x, y, 30)
        if close_pixel is not None:
            path = seg.find_path_bis(close_pixel[0], close_pixel[1], self.graph, self.lookup_table)

            # highlighted_img = seg.highlight_path(img.shape, path)
            self.viewer.add_path_to_scene(path)

    def get_path_measurements(self, path_obj, text_obj):
        self.path_meas_list.append([path_obj, text_obj])

        self.pushButton_show_linemeas.setEnabled(True)
        self.pushButton_show_linemeas.setChecked(True)

    def hand_pan(self):
        # update status
        self.update_progress(text='You can drag/pan the image')
        # switch back to hand tool
        self.viewer.point_selection = False
        self.viewer.line_meas = False
        self.viewer.painting = False

        self.actionHand_selector.setChecked(True)
        if not self.viewer.hand_drag:
            self.viewer.toggleDragMode()

    # viewer __________________________________________
    def update_view(self):
        if self.pushButton_show_image.isChecked():
            if self.pushButton_show_mask.isChecked():
                if self.has_mask:
                    self.viewer.compose_mask_image(self.output_color_mask)
                    self.viewer.clean_scene()
            elif self.pushButton_show_skel.isChecked():
                self.viewer.compose_mask_image(self.output_color_skeleton)
                # add markers to image
                self.viewer.add_nodes(self.junctions, self.endpoints)
            else:
                self.viewer.clean_scene()
                self.viewer.setPhoto(QPixmap(self.image_path))
        else:
            if self.pushButton_show_mask.isChecked():
                if self.has_mask:
                    self.viewer.compose_mask_image(self.output_color_mask)
                    self.viewer.clean_scene()
                    self.viewer.clean_scene()
                    self.viewer.setPhoto(QPixmap(self.output_color_mask))

            elif self.pushButton_show_skel.isChecked():
                self.viewer.setPhoto(QPixmap(self.output_color_skeleton))
                # add markers to image
                self.viewer.add_nodes(self.junctions, self.endpoints)
            else:
                # Load the existing image
                original_image = QImage(self.image_path)  # Replace with your image path

                # Create a new white image of the same size
                white_image = QImage(original_image.size(), QImage.Format_ARGB32)
                white_image.fill(Qt.white)  # Fill the image with white color

                # Convert the white QImage to QPixmap
                white_pixmap = QPixmap.fromImage(white_image)
                self.viewer.clean_scene()
                self.viewer.setPhoto(white_pixmap)

    def compute_all_outputs_from_binary(self, binary):
        color_mask = seg.binary_to_color_mask(binary)
        skel = seg.binary_to_skeleton(binary)
        color_skel = seg.binary_to_color_mask(skel)

        # save the 4 images
        image = Image.fromarray(binary)
        image.save(self.output_binary_mask)
        image = Image.fromarray(color_mask)
        image.save(self.output_color_mask)
        image = Image.fromarray(skel)
        image.save(self.output_skeleton)
        image = Image.fromarray(color_skel)
        image.save(self.output_color_skeleton)

        # compute junctions from skeleton image
        self.junctions, self.endpoints = seg.find_junctions_endpoints(self.output_skeleton)
        self.graph = seg.build_graph(self.junctions, self.endpoints, skel)
        self.lookup_table = seg.segment_lookup_table(self.graph)

        # seg.visualize_graph(self.graph, skel)

    # other scientific functions __________________________________________
    def set_scale(self):
        dialog = ScaleDialog()
        if dialog.exec_():
            self.resolution = dialog.resolution
            print(f'New resolution is {self.resolution} mm/pixel')
            self.viewer.mm_per_pixel = self.resolution

            self.toggle_all_meas()
            self.toggle_all_meas()

    def go_segment(self):
        # execute YOLO script
        self.hand_pan()

        self.update_progress(text="Segmenting image with yolo!", nb=0)

        result = seg.get_segmentation_result(self.helper, self.image_path)
        binary = seg.create_binary_from_yolo(result)

        self.compute_all_outputs_from_binary(binary)
        self.has_mask = True

        self.update_progress(text="You can now modify the mask!", nb=100)

        self.pushButton_show_mask.setEnabled(True)
        self.pushButton_show_skel.setEnabled(True)
        self.pushButton_show_mask.setChecked(True)

        self.actionMeasure_path.setEnabled(True)

        self.update_view()

    def update_yolo_steps(self, text):
        def extract_numbers(input_string):
            # This regex pattern looks for two groups of one or more digits,
            # separated by a non-digit character (like '/')
            match = re.search(r'(\d+)[^\d]+(\d+)', input_string)
            if match:
                first_number = int(match.group(1))
                second_number = int(match.group(2))
                return first_number, second_number
            else:
                return None, None

        i, num_slices = extract_numbers(text)
        print(i, num_slices)
        self.update_progress(text=f'Segmenting slice {i}/{num_slices}', nb=i/num_slices*100)
    def onOutput(self, text):
        if text == 'read':
            # Handle 'read' emission here
            self.update_progress(text=text)
        else:
            pass

    # load data __________________________________________
    def get_image(self):
        """
        Get the image path from the user
        :return:
        """
        try:
            img = QFileDialog.getOpenFileName(self, u"Ouverture de fichiers", "",
                                              "Image Files (*.png *.jpg *.JPEG *.bmp *.tif)")
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
        self.viewer.setPhoto(QPixmap(path), fit_view=True)
        self.viewer.set_base_image(path)
        self.image_loaded = True

        self.hand_pan()

        # enable action
        self.actionSegment.setEnabled(True)
        self.actionMeasure.setEnabled(True)
        self.actionSet_scale.setEnabled(True)
        self.actionPaint_mask.setEnabled(True)
        self.actionEraser_mask.setEnabled(True)
        self.actionHand_selector.setEnabled(True)
        self.actionHand_selector.setChecked(True)

        self.pushButton_show_image.setEnabled(True)
        self.pushButton_show_image.setChecked(True)
        self.pushButton_export.setEnabled(True)
        self.pushButton_export_view.setEnabled(True)

    # export data __________________________________________
    def export_current_view(self):
        # Create a QImage with the size of the viewport
        image = QImage(self.viewer.viewport().size(), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        # Paint the QGraphicsView's viewport onto the QImage
        painter = QPainter(image)
        self.viewer.render(painter)
        painter.end()

        # Open 'Save As' dialog
        file_path, _ = QFileDialog.getSaveFileName(
            None, "Save Image", "", "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg *.JPEG)"
        )

        # Save the image if a file path was provided, using high-quality settings for JPEG
        if file_path:
            if file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
                image.save(file_path, 'JPEG', 100)
            else:
                image.save(file_path)  # PNG is lossless by default

    def export_view(self):
        # Get the scene from QGraphicsView
        scene = self.viewer._scene

        # Create a QImage with the size of the scene
        image = QImage(scene.sceneRect().size().toSize(), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)

        # Paint the scene onto the QImage
        painter = QPainter(image)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing, False)
        scene.render(painter)
        painter.end()

        # Open 'Save As' dialog
        file_path, _ = QFileDialog.getSaveFileName(
            None, "Save Image", "", "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)"
        )

        # Save the image if a file path was provided, using high-quality settings for JPEG
        if file_path:
            if file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
                image.save(file_path, 'JPEG', 100)
            else:
                image.save(file_path)  # PNG is lossless by default


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
            QPushButton:disabled {
                background-color: #666;
            }
            QWidget { background-color: #444; }
            QProgressBar {
                text-align: center;
                color: rgb(240, 240, 240);
                border-width: 1px; 
                border-radius: 10px;
                border-color: rgb(230, 230, 230);
                border-style: solid;
                background-color:rgb(207,207,207);
            }
                
            QProgressBar:chunk {
                background-color:rgb(50, 156, 179);
                border-radius: 10px;
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
