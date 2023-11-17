# standard libraries
import numpy as np
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtUiTools import QUiLoader
import resources as res


class UiLoader(QUiLoader):
    """
    Subclass :class:`~PySide.QtUiTools.QUiLoader` to create the user interface
    in a base instance.

    Unlike :class:`~PySide.QtUiTools.QUiLoader` itself this class does not
    create a new instance of the top-level widget, but creates the user
    interface in an existing instance of the top-level class.

    This mimics the behaviour of :func:`PyQt4.uic.loadUi`.
    """

    def __init__(self, baseinstance, customWidgets=None):
        """
        Create a loader for the given ``baseinstance``.

        The user interface is created in ``baseinstance``, which must be an
        instance of the top-level class in the user interface to load, or a
        subclass thereof.

        ``customWidgets`` is a dictionary mapping from class name to class object
        for widgets that you've promoted in the Qt Designer interface. Usually,
        this should be done by calling registerCustomWidget on the QUiLoader, but
        with PySide 1.1.2 on Ubuntu 12.04 x86_64 this causes a segfault.

        ``parent`` is the parent object of this loader.
        """

        QUiLoader.__init__(self, baseinstance)
        self.baseinstance = baseinstance
        self.customWidgets = customWidgets

    def createWidget(self, class_name, parent=None, name=''):
        """
        Function that is called for each widget defined in ui file,
        overridden here to populate baseinstance instead.
        """

        if parent is None and self.baseinstance:
            # supposed to create the top-level widget, return the base instance
            # instead
            return self.baseinstance

        else:
            if class_name in self.availableWidgets():
                # create a new widget for child widgets
                widget = QUiLoader.createWidget(self, class_name, parent, name)

            else:
                # if not in the list of availableWidgets, must be a custom widget
                # this will raise KeyError if the user has not supplied the
                # relevant class_name in the dictionary, or TypeError, if
                # customWidgets is None
                try:
                    widget = self.customWidgets[class_name](parent)

                except (TypeError, KeyError) as e:
                    raise Exception(
                        'No custom widget ' + class_name + ' found in customWidgets param of UiLoader __init__.')

            if self.baseinstance:
                # set an attribute for the new child widget on the base
                # instance, just like PyQt4.uic.loadUi does.
                setattr(self.baseinstance, name, widget)

                # this outputs the various widget names, e.g.
                # sampleGraphicsView, dockWidget, samplesTableView etc.
                # print(name)

            return widget


def loadUi(uifile, baseinstance=None, customWidgets=None,
           workingDirectory=None):
    """
    Dynamically load a user interface from the given ``uifile``.

    ``uifile`` is a string containing a file name of the UI file to load.

    If ``baseinstance`` is ``None``, the a new instance of the top-level widget
    will be created.  Otherwise, the user interface is created within the given
    ``baseinstance``.  In this case ``baseinstance`` must be an instance of the
    top-level widget class in the UI file to load, or a subclass thereof.  In
    other words, if you've created a ``QMainWindow`` interface in the designer,
    ``baseinstance`` must be a ``QMainWindow`` or a subclass thereof, too.  You
    cannot load a ``QMainWindow`` UI file with a plain
    :class:`~PySide.QtGui.QWidget` as ``baseinstance``.

    ``customWidgets`` is a dictionary mapping from class name to class object
    for widgets that you've promoted in the Qt Designer interface. Usually,
    this should be done by calling registerCustomWidget on the QUiLoader, but
    with PySide 1.1.2 on Ubuntu 12.04 x86_64 this causes a segfault.

    :method:`~PySide.QtCore.QMetaObject.connectSlotsByName()` is called on the
    created user interface, so you can implemented your slots according to its
    conventions in your widget class.

    Return ``baseinstance``, if ``baseinstance`` is not ``None``.  Otherwise
    return the newly created instance of the user interface.
    """

    loader = UiLoader(baseinstance, customWidgets)

    if workingDirectory is not None:
        loader.setWorkingDirectory(workingDirectory)

    widget = loader.load(uifile)
    QMetaObject.connectSlotsByName(widget)
    return widget


class ImageDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Image Viewer")
        self.setLayout(QVBoxLayout())

        label = QLabel()
        pixmap = QPixmap.fromImage(image)
        label.setPixmap(pixmap)

        self.layout().addWidget(label)


def QPixmapFromItem(item):
    """
    Transform a QGraphicsitem into a Pixmap
    :param item: QGraphicsItem
    :return: QPixmap
    """
    pixmap = QPixmap(item.boundingRect().size().toSize())
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    # this line seems to be needed for all items except of a LineItem...
    painter.translate(-item.boundingRect().x(), -item.boundingRect().y())
    painter.setRenderHint(QPainter.Antialiasing, True)
    opt = QStyleOptionGraphicsItem()
    item.paint(painter, opt)  # here in some cases the self is needed
    return pixmap


def QPixmapToArray(pixmap):
    ## Get the size of the current pixmap
    size = pixmap.size()
    h = size.width()
    w = size.height()

    ## Get the QImage Item and convert it to a byte string
    qimg = pixmap.toImage()
    byte_str = qimg.bits().tobytes()

    ## Using the np.frombuffer function to convert the byte string into an np array
    img = np.frombuffer(byte_str, dtype=np.uint8).reshape((w, h, 4))

    return img


class CircularPixmapItem(QGraphicsRectItem):
    def __init__(self, pixmap, size, parent=None):
        super().__init__(-size / 2, -size / 2, size, size, parent)
        self.pixmap = pixmap
        self.size = size

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addEllipse(self.rect())
        painter.setClipPath(path)

        # Correct the drawPixmap call
        targetRect = self.rect().toRect()  # Convert QRectF to QRect
        painter.drawPixmap(targetRect, self.pixmap, self.pixmap.rect())


class MagnifyingGlass(QGraphicsEllipseItem):
    def __init__(self, size=200, border_width=5, parent=None):
        self._size = size
        super().__init__(-self._size / 2, -self._size / 2, self._size, self._size, parent)
        self.setBrush(Qt.transparent)
        self.pen = QPen()
        self.pen.setStyle(Qt.DashDotLine)
        self.pen.setWidth(border_width)
        self.pen.setColor(QColor(255, 255, 255, a=200))

        self.setPen(self.pen)
        self.pixmap_item = QGraphicsPixmapItem(self)
        self.pixmap_item.setPos(-self._size / 2, -self._size / 2)
        self.setZValue(1)

    def update_size(self, new_size):
        self._size = new_size

        # Update the ellipse size
        self.setRect(-self._size / 2, -self._size / 2, self._size, self._size)

    def set_pixmap(self, pixmap):
        # Remove the old pixmap item if it exists
        if hasattr(self, 'pixmap_item'):
            self.scene().removeItem(self.pixmap_item)

        # Create and add the new circular pixmap item
        self.pixmap_item = CircularPixmapItem(pixmap, self._size, self)
        self.pixmap_item.setPos(0, 0)


class PhotoViewer(QGraphicsView):
    photoClicked = Signal(list)
    endDrawing_rect = Signal()
    endDrawing_line_meas = Signal(QGraphicsLineItem, QGraphicsTextItem)
    pathAdded = Signal(QGraphicsPathItem, QGraphicsTextItem)
    endPainting = Signal(np.ndarray)
    endErasing = Signal()

    def __init__(self, parent):
        super(PhotoViewer, self).__init__(parent)
        self._zoom = 0
        self._empty = True
        self._scene = QGraphicsScene(self)
        self._photo = QGraphicsPixmapItem()
        self._scene.addItem(self._photo)
        self.setScene(self._scene)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setBackgroundBrush(QBrush(QColor(255, 255, 255)))
        self.setFrameShape(QFrame.NoFrame)

        self.sourceImage = QImage()
        self.destinationImage = QImage()

        self.scale_bar_length_mm = 1  # Length of the scale bar in mm
        self.mm_per_pixel = None  # Scale of the image in mm/pixel

        self.setMouseTracking(True)
        self.origin = QPoint()

        self.hand_drag = True

        # tools activation
        self.line_meas = False
        self.point_selection = False
        self.painting = False
        self.eraser = False

        # current items
        self._current_point = None
        self._current_line_item = None
        self._current_text_item = None
        self._current_path_item = None

        # pens and brushes
        self.pen = QPen()
        self.pen.setStyle(Qt.DashDotLine)
        self.pen.setWidth(4)
        self.pen.setColor(QColor(255, 0, 0, a=255))
        self.pen.setCapStyle(Qt.RoundCap)
        self.pen.setJoinStyle(Qt.RoundJoin)

        self.meas_color = QColor(0, 100, 255, a=255)
        self.pen_yolo = QPen()
        # self.pen.setStyle(Qt.DashDotLine)
        self.pen_yolo.setWidth(3)
        self.pen_yolo.setColor(self.meas_color)
        self.pen_yolo.setCapStyle(Qt.RoundCap)
        self.pen_yolo.setJoinStyle(Qt.RoundJoin)

        # for painting functionalities
        self.brush = QPen()
        self.brush.setWidth(30)
        self.brush.setColor(QColor(0, 255, 0, a=100))
        self.brush.setCapStyle(Qt.RoundCap)
        self.brush.setJoinStyle(Qt.RoundJoin)

        # for painting functionalities
        self.eraser_brush = QPen()
        self.eraser_brush.setWidth(30)
        self.eraser_brush.setColor(QColor(255, 0, 0, a=100))
        self.eraser_brush.setCapStyle(Qt.RoundCap)
        self.eraser_brush.setJoinStyle(Qt.RoundJoin)

        # initial text size
        self.text_font_size = 0
        self.line_size = 0

        # custom paint cursor
        self.prefered_cursor_diam = None
        self.brush_cur = None

        # magnifying glass
        self.right_mouse_pressed = False
        self.middle_mouse_pressed = False

        self.magnifying_glass_size = 400  # Adjust this value to change the size
        self.magnifying_factor = 4
        self.magnifying_glass = None

    def has_photo(self):
        return not self._empty

    def drawBackground(self, painter, rect):
        # Fill the background with black color
        painter.fillRect(rect, QColor(0, 0, 0))  # RGB values for black

    def add_all_line_measurements(self, line_data, path_data=None):
        for line in line_data:
            self._scene.addItem(line[0])  # line item
            self._scene.addItem(line[1])  # text item

            if self.mm_per_pixel is not None:
                text_content = line[1].toPlainText()
                numeric_part = text_content.split()[0]
                distance = float(numeric_part)
                line[1].setPlainText(
                    f'{distance:.2f} pixels \n {distance * self.mm_per_pixel:.2f} mm')

    def add_all_path_measurements(self, path_data):
        for path in path_data:
            self._scene.addItem(path[0])  # line item
            self._scene.addItem(path[1])  # text item

    def draw_scale_bar(self, painter):
        current_scale_factor = self.transform().m11()
        length_in_pixels = self.scale_bar_length_mm / self.mm_per_pixel * current_scale_factor

        # Adjust the scale if the length in pixels is too small
        display_scale_bar_length_mm = self.scale_bar_length_mm
        while length_in_pixels < 100:  # Set your preferred minimum length threshold here
            display_scale_bar_length_mm *= 10
            length_in_pixels = display_scale_bar_length_mm / self.mm_per_pixel * current_scale_factor

        # Position the scale bar in the middle horizontally, at the bottom vertically
        x = (self.viewport().width() - length_in_pixels) / 2
        y = self.viewport().height() - 40  # Adjusted to give space for text

        # Set pen for scale bar border
        painter.setPen(QColor(0, 0, 255))  # Blue border
        painter.setBrush(QColor(255, 255, 255))  # White fill
        painter.drawRect(x, y, length_in_pixels, 10)

        # Draw text in bold
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        text = f"{display_scale_bar_length_mm:.2f} mm"
        painter.setPen(QColor(0, 0, 255))  # Blue text

        # Calculate text position
        text_rect = painter.fontMetrics().boundingRect(text)
        text_x = x + (length_in_pixels - text_rect.width()) / 2
        text_y = y - 5  # Slightly above the scale bar

        painter.drawText(text_x, text_y, text)

    def paintEvent(self, event):
        super().paintEvent(event)  # Draw the scene
        painter = QPainter(self.viewport())
        if self.mm_per_pixel != None:
            self.draw_scale_bar(painter)

    def fitInView(self, scale=True):
        rect = QRectF(self._photo.pixmap().rect())
        if not rect.isNull():
            self.setSceneRect(rect)
            if self.has_photo():
                unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
                print('unity: ', unity)
                self.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.viewport().rect()
                print('view: ', viewrect)
                scenerect = self.transform().mapRect(rect)
                print('scene: ', viewrect)
                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())
                self.scale(factor, factor)
            self._zoom = 0

    def clean_scene(self):
        for item in self._scene.items():
            print(type(item))
            if isinstance(item, QGraphicsEllipseItem):
                self._scene.removeItem(item)
            elif isinstance(item, QGraphicsPolygonItem):
                self._scene.removeItem(item)

    def clean_scene_line(self):
        for item in self._scene.items():
            print(type(item))
            if isinstance(item, QGraphicsLineItem):
                self._scene.removeItem(item)

    def clean_scene_poly(self):
        for item in self._scene.items():
            print(type(item))
            if isinstance(item, QGraphicsPolygonItem):
                self._scene.removeItem(item)

    def clean_scene_text(self):
        for item in self._scene.items():
            print(type(item))
            if isinstance(item, QGraphicsTextItem):
                self._scene.removeItem(item)

    def clean_scene_path(self):
        for item in self._scene.items():
            print(type(item))
            if isinstance(item, QGraphicsPathItem):
                self._scene.removeItem(item)

    def add_nodes(self, junctions, endpoints):
        # Calculate scale factor (adjust as needed)
        scale_factor = 5

        # Add markers for junctions
        for y, x in junctions:
            ellipse = QGraphicsEllipseItem(
                QRectF(x - scale_factor // 2, y - scale_factor // 2, scale_factor, scale_factor))
            ellipse.setPen(QPen(QColor("red")))
            self._scene.addItem(ellipse)

        # Add markers for endpoints
        for y, x in endpoints:
            ellipse = QGraphicsEllipseItem(
                QRectF(x - scale_factor // 2, y - scale_factor // 2, scale_factor, scale_factor))
            ellipse.setPen(QPen(QColor("blue")))
            self._scene.addItem(ellipse)

    def change_to_brush_cursor(self):
        self.setCursor(self.brush_cur)

    def create_circle_cursor(self, diameter):
        # Create a QPixmap with a transparent background
        self.cursor_diameter = diameter

        scale_factor = self.transform().m11()
        print(f'scale factor: {scale_factor}')
        scaledDiameter = diameter * scale_factor

        pixmap = QPixmap(scaledDiameter, scaledDiameter)
        pixmap.fill(Qt.transparent)

        # Create a QPainter to draw on the pixmap
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw a circle
        painter.setPen(QColor(0, 0, 0))  # Black color, you can change as needed
        painter.drawEllipse(0, 0, scaledDiameter - 1, scaledDiameter - 1)

        # End painting
        painter.end()

        # Create a cursor from the pixmap
        return QCursor(pixmap)

    def compose_mask_image(self, image_path):
        self.destinationImage.load(image_path)
        painter = QPainter(self.resultImage)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.resultImage.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(0, 0, self.destinationImage)
        painter.setCompositionMode(QPainter.CompositionMode_Screen)
        painter.drawImage(0, 0, self.sourceImage)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationOver)
        painter.fillRect(self.resultImage.rect(), QColor(255, 255, 255))
        painter.end()

        self.setPhoto(QPixmap.fromImage(self.resultImage))

    def set_base_image(self, path):
        self.sourceImage.load(path)
        self.resultSize = self.sourceImage.size()
        self.resultImage = QImage(self.resultSize, QImage.Format_ARGB32_Premultiplied)

    def setPhoto(self, pixmap=None, fit_view=False):
        if pixmap and not pixmap.isNull():
            self._empty = False
            self._photo.setPixmap(pixmap)
            self.scene_image = pixmap.toImage()

            # initial text size
            self.original_text_font_size = int(self.scene().width() / 160)
            self.text_font_size = int(self.scene().width() / 160)

            # intial line size
            self.line_size = int(self.text_font_size / 4)
            self.pen_yolo.setWidth(self.line_size)

            # adapt magnifier border
            self.magnifying_glass_size = int(self.scene().width() / 10)
            self.magnifying_glass = MagnifyingGlass(self.magnifying_glass_size, border_width=self.line_size*3)
            self._scene.addItem(self.magnifying_glass)
            # Temporarily hide the magnifying glass to avoid rendering it
            self.magnifying_glass.hide()


            if fit_view:
                self.fitInView()

                # initial cursor size
                self.prefered_cursor_diam = int(self.scene().width() / 75)
                print(f'initial brush diam: {self.prefered_cursor_diam}')
                self.brush_cur = self.create_circle_cursor(self.prefered_cursor_diam)

        else:
            self._empty = True
            self.setDragMode(QGraphicsView.NoDrag)
            self._photo.setPixmap(QPixmap())

    def toggleDragMode(self):
        if self.line_meas or self.point_selection or self.painting:
            self.setDragMode(QGraphicsView.NoDrag)
            self.hand_drag = False
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.hand_drag = True

    def add_poly(self, coordinates):
        # Create a QPolygonF from the coordinates
        polygon = QPolygonF()
        for x, y in coordinates:
            polygon.append(QPointF(x, y))

        # Create a QGraphicsPolygonItem and set its polygon
        polygon_item = QGraphicsPolygonItem(polygon)
        fill_color = QColor(0, 255, 255, 100)
        polygon_item.setBrush(fill_color)  # Set fill color

        # Add the QGraphicsPolygonItem to the scene
        self._scene.addItem(polygon_item)

    def add_list_poly(self, list_objects):
        for el in list_objects:
            # Create a QPolygonF from the coordinates
            polygon = QPolygonF()
            for x, y in el.coords:
                polygon.append(QPointF(x, y))

            # Create a QGraphicsPolygonItem and set its polygon
            polygon_item = QGraphicsPolygonItem(polygon)
            fill_color = QColor(0, 255, 255, 100)
            polygon_item.setBrush(fill_color)  # Set fill color

            # Add the QGraphicsPolygonItem to the scene
            self._scene.addItem(polygon_item)

    def get_coord(self, QGraphicsRect):
        rect = QGraphicsRect.rect()
        coord = [rect.topLeft(), rect.bottomRight()]
        print(coord)

        return coord

    def get_selected_point(self):
        print(self._current_point)
        self.draw_ellipse(self._current_point)
        return self._current_point

    def draw_ellipse(self, point, type):
        # test color
        image = self._photo.pixmap().toImage()

        sum_red, sum_green, sum_blue = 0, 0, 0
        region_size = 20

        # Define the region around the point
        x_start = max(0, int(point.x()) - region_size // 2)
        y_start = max(0, int(point.y()) - region_size // 2)

        x_end = min(image.width(), int(point.x()) + region_size // 2)
        y_end = min(image.height(), int(point.y()) + region_size // 2)

        num_pixels = (x_end - x_start) * (y_end - y_start)

        # Iterate over all the pixels in this region
        for x in range(x_start, x_end):
            for y in range(y_start, y_end):
                pixel_color = image.pixelColor(x, y)
                sum_red += pixel_color.red()
                sum_green += pixel_color.green()
                sum_blue += pixel_color.blue()

        # Calculate the average RGB value for the entire region
        avg_rgb = (sum_red + sum_green + sum_blue) / (3 * num_pixels)

        # Depending on the average value, set the text color
        if avg_rgb > 125:
            text_color = QColor(Qt.black)
        else:
            text_color = QColor(Qt.white)

        if type == 'plus':
            color = QColor(Qt.cyan)
            text_item = self._scene.addText(str(self.pluspoint_count))
        else:
            color = QColor(Qt.red)
            text_item = self._scene.addText(str(self.minpoint_count))

        self._scene.addEllipse(point.x() - self.point_size / 2, point.y() - self.point_size / 2, self.point_size,
                               self.point_size, QPen(color), color)

        text_item.setDefaultTextColor(text_color)
        text_item.setPos(point.x(), point.y())

        font = QFont()
        font.setPointSize(self.text_size)
        font.setBold(True)  # Make the text bold
        text_item.setFont(font)

    def update_all_text_size(self):
        print(f'update font size: {self.text_font_size}')
        for item in self._scene.items():
            if isinstance(item, QGraphicsTextItem):
                font = QFont()
                font.setPointSize(self.text_font_size)
                font.setBold(True)  # Make the text bold
                item.setFont(font)

                text_width = item.boundingRect().width()
                text_height = item.boundingRect().height()
                # item.setPos(mid_x - text_width / 2, mid_y - text_height / 2)

    def update_all_line_size(self):
        print(f'update line size: {self.line_size}')
        for item in self._scene.items():
            if isinstance(item, QGraphicsLineItem) or isinstance(item, QGraphicsPathItem):
                self.pen_yolo.setWidth(self.line_size)
                item.setPen(self.pen_yolo)

    def update_font_and_line_size(self):
        # Adjust font size based on the zoom level
        if self._zoom >= 0:
            scale_factor = 1 / (1 + 0.25 * self._zoom)  # Adjust scaling factor as needed
        else:
            scale_factor = 1 + abs(self._zoom) * 0.2  # Adjust scaling factor for zoom out

        self.text_font_size = int(self.original_text_font_size * scale_factor)
        self.line_size = int(self.text_font_size / 4)

        self.update_all_text_size()  # Function to update the text size in your view
        self.update_all_line_size()

    def update_magnifier_wheel(self, event):
        scene_pos = self.mapToScene(event.position().toPoint())

        # Adjust these values for desired magnification
        magnify_factor = self.magnifying_factor

        # Calculate the dimensions of the sub-pixmap to grab
        grab_width = self.magnifying_glass_size // magnify_factor
        grab_height = self.magnifying_glass_size // magnify_factor

        # Calculate the top-left corner of the sub-pixmap to grab, such that the cursor is centered
        grab_x = scene_pos.x() - grab_width / 2
        grab_y = scene_pos.y() - grab_height / 2

        # Extract the portion of the rendered scene around the cursor
        sub_image = self.scene_image.copy(grab_x, grab_y, grab_width, grab_height)

        # Convert QImage to QPixmap and scale it to achieve magnification
        magnified_pixmap = QPixmap.fromImage(sub_image).scaled(self.magnifying_glass_size,
                                                               self.magnifying_glass_size,
                                                               Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Update the magnifying glass
        self.magnifying_glass.setPos(scene_pos)
        self.magnifying_glass.update_size(self.magnifying_glass_size)
        self.magnifying_glass.set_pixmap(magnified_pixmap)

    # mouse events
    def wheelEvent(self, event):
        if self.right_mouse_pressed:
            if event.modifiers() & Qt.ControlModifier:
                if event.angleDelta().y() > 0:
                    factor = 1.25
                    self.magnifying_glass_size *= factor
                    self.update_magnifier_wheel(event)

                else:
                    factor = 0.8
                    self.magnifying_glass_size *= factor
                    self.update_magnifier_wheel(event)

            elif event.modifiers() & Qt.ShiftModifier:
                if event.angleDelta().y() > 0:
                    factor = 1.25
                    self.magnifying_factor *= factor
                    self.update_magnifier_wheel(event)

                else:
                    factor = 0.8
                    self.magnifying_factor *= factor
                    self.update_magnifier_wheel(event)

        elif event.modifiers() & Qt.ShiftModifier:
            if self.painting or self.point_selection:
                if event.angleDelta().y() > 0:
                    factor = 1.25
                    self.prefered_cursor_diam *= factor
                    self.cursor_diameter *= factor
                    self.brush_cur = self.create_circle_cursor(self.cursor_diameter)
                    self.change_to_brush_cursor()

                    # adapt brush drawing size:
                    print(self.prefered_cursor_diam)
                    self.brush.setWidth(self.prefered_cursor_diam)
                    self.eraser_brush.setWidth(self.prefered_cursor_diam)


                else:
                    factor = 0.8

                    self.prefered_cursor_diam *= factor
                    self.cursor_diameter *= factor
                    self.brush_cur = self.create_circle_cursor(self.cursor_diameter)
                    self.change_to_brush_cursor()

                    # adapt brush drawing size:
                    self.brush.setWidth(self.prefered_cursor_diam)
                    self.eraser_brush.setWidth(self.prefered_cursor_diam)


        elif self.has_photo():
            if event.angleDelta().y() > 0:
                factor = 1.25
                self._zoom += 1

            else:
                factor = 0.8
                self._zoom -= 1

            if self._zoom > 0:
                self.scale(factor, factor)

            elif self._zoom == 0:
                self.fitInView()

            else:
                self._zoom = 0

            # adapt paint cursor
            if self.painting or self.point_selection:
                self.brush_cur = self.create_circle_cursor(self.prefered_cursor_diam)
                self.change_to_brush_cursor()

            self.viewport().update()
            self.update_font_and_line_size()
            self.update_all_text_size()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.line_meas:
                self._current_line_item = QGraphicsLineItem()
                self._current_line_item.setPen(self.pen_yolo)

                self._current_text_item = QGraphicsTextItem()  # Format the distance to 2 decimal places
                self._current_text_item.setZValue(1)
                self._scene.addItem(self._current_text_item)

                self._scene.addItem(self._current_line_item)
                self.origin = self.mapToScene(event.pos())

                self._current_line_item.setLine(QLineF(self.origin, self.origin))

            # detect cracks by click
            elif self.point_selection:
                self._current_point = self.mapToScene(event.pos())
                self.photoClicked.emit([int(self._current_point.x()), int(self._current_point.y())])

            # paint crack on mask
            elif self.painting:
                self.origin = self.mapToScene(event.pos())
                self._current_path = QPainterPath(self.origin)

                self._current_path_item = QGraphicsPathItem()
                self._current_path_item.setPath(self._current_path)
                if self.eraser:
                    self._current_path_item.setPen(self.eraser_brush)
                else:
                    self._current_path_item.setPen(self.brush)

                self._scene.addItem(self._current_path_item)

        elif event.button() == Qt.RightButton:
            if self.has_photo():
                self.right_mouse_pressed = True
                print('right click!')

        elif event.button() == Qt.MiddleButton:
            self.middle_mouse_pressed = True
            self._lastMousePosition = event.pos()

        super(PhotoViewer, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.middle_mouse_pressed:
            delta = event.pos() - self._lastMousePosition
            self._lastMousePosition = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())

        elif self.right_mouse_pressed:
            scene_pos = self.mapToScene(event.pos())

            # Adjust these values for desired magnification
            magnify_factor = self.magnifying_factor

            # Calculate the dimensions of the sub-pixmap to grab
            grab_width = self.magnifying_glass_size // magnify_factor
            grab_height = self.magnifying_glass_size // magnify_factor

            # Calculate the top-left corner of the sub-pixmap to grab, such that the cursor is centered
            grab_x = scene_pos.x() - grab_width / 2
            grab_y = scene_pos.y() - grab_height / 2

            # Extract the portion of the rendered scene around the cursor
            sub_image = self.scene_image.copy(grab_x, grab_y, grab_width, grab_height)

            # Convert QImage to QPixmap and scale it to achieve magnification
            magnified_pixmap = QPixmap.fromImage(sub_image).scaled(self.magnifying_glass_size,
                                                                   self.magnifying_glass_size,
                                                                   Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # Update the magnifying glass
            self.magnifying_glass.setPos(scene_pos)
            self.magnifying_glass.set_pixmap(magnified_pixmap)
            self.magnifying_glass.setZValue(2)
            self.magnifying_glass.show()

        elif self.line_meas:
            if self._current_line_item is not None:
                self.new_coord = self.mapToScene(event.pos())
                self._current_line_item.setLine(QLineF(self.origin, self.new_coord))

                # compute line values
                p1 = np.array([int(self.origin.x()), int(self.origin.y())])
                p2 = np.array([int(self.new_coord.x()), int(self.new_coord.y())])

                distance = np.linalg.norm(p2 - p1)

                # Calculate midpoint
                mid_x = (self.origin.x() + self.new_coord.x()) / 2
                mid_y = (self.origin.y() + self.new_coord.y()) / 2

                # update text
                if self.mm_per_pixel is None:
                    self._current_text_item.setPlainText(f'{distance:.2f} pixels')

                else:
                    self._current_text_item.setPlainText(
                        f'{distance:.2f} pixels \n {distance * self.mm_per_pixel:.2f} mm')

                text_width = self._current_text_item.boundingRect().width()
                text_height = self._current_text_item.boundingRect().height()
                self._current_text_item.setPos(mid_x - text_width / 2, mid_y - text_height / 2)  # TODO Improve
                self._current_text_item.setDefaultTextColor(QColor("blue"))
                font = QFont()
                font.setPointSize(self.text_font_size)
                font.setBold(True)  # Make the text bold
                self._current_text_item.setFont(font)

        elif self.painting:
            if self._current_path_item is not None:
                new_coord = self.mapToScene(event.pos())
                self._current_path.lineTo(new_coord)
                self._current_path_item.setPath(self._current_path)

        super(PhotoViewer, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.middle_mouse_pressed = False

        elif event.button() == Qt.RightButton:
            self.right_mouse_pressed = False
            self.magnifying_glass.hide()

        elif self.line_meas:
            self.line_meas = False

            if self._current_line_item is not None:
                # emit signal (end of measure)
                self.endDrawing_line_meas.emit(self._current_line_item, self._current_text_item)
                print('Line meas. added')

            self.origin = QPoint()
            self._current_line_item = None
            self._current_text_item = None

        elif self.painting:
            if self._current_path_item is not None:
                # create pixmap from item
                pixmap = QPixmapFromItem(self._current_path_item)
                image = QPixmapToArray(pixmap)
                gray = np.dot(image[..., :3], [0.2989, 0.5870, 0.1140])

                coords = np.column_stack(np.where(gray > 2))

                bb_rect = self._current_path_item.sceneBoundingRect()
                top_left = bb_rect.topLeft()

                limit_row = int(top_left.x())
                limit_col = int(top_left.y())
                print(f'limits = {limit_row}, {limit_col}')

                coords[:, 0] += limit_col
                coords[:, 1] += limit_row

                self.endPainting.emit(coords)
                print('brush ROI added')

                # remove path
                self._scene.removeItem(self._current_path_item)

            self.origin = QPoint()
            self._current_path_item = None

        super(PhotoViewer, self).mouseReleaseEvent(event)

    def find_extreme_and_middle_points(self, path):
        min_x = min(path, key=lambda p: p[0])[0]
        max_x = max(path, key=lambda p: p[0])[0]
        min_y = min(path, key=lambda p: p[1])[1]
        max_y = max(path, key=lambda p: p[1])[1]

        extreme_points = ((min_x, min_y), (max_x, max_y))
        middle_point = ((min_x + max_x) / 2, (min_y + max_y) / 2)

        return extreme_points, middle_point

    def add_path_to_scene(self, path):
        if len(path) < 2:
            return  # Need at least two points to draw a path

        painter_path = QPainterPath()
        painter_path.moveTo(QPointF(path[0][1], path[0][0]))  # Start at the first point

        for x, y in path[1:]:
            painter_path.lineTo(QPointF(y, x))  # Add line to each point

        path_item = QGraphicsPathItem(painter_path)
        path_item.setPen(self.pen_yolo)
        self._scene.addItem(path_item)

        # print length of path
        text_item = QGraphicsTextItem()  # Format the distance to 2 decimal places
        text_item.setZValue(1)
        if self.mm_per_pixel is None:
            text_item.setPlainText(f'{len(path):.2f} pixels')

        else:
            text_item.setPlainText(
                f'{len(path):.2f} pixels \n {len(path) * self.mm_per_pixel:.2f} mm')

        # get middle point of path
        extreme_points, middle_point = self.find_extreme_and_middle_points(path)
        text_item.setPos(middle_point[1], middle_point[0])

        # style
        text_item.setDefaultTextColor(QColor("blue"))
        font = QFont()
        font.setPointSize(self.text_font_size)
        font.setBold(True)  # Make the text bold
        text_item.setFont(font)
        self._scene.addItem(text_item)

        self.pathAdded.emit(path_item, text_item)
