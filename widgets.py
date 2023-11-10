# standard libraries
import numpy as np
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtUiTools import QUiLoader


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
class PhotoViewer(QGraphicsView):
    photoClicked = Signal(QPoint)
    endDrawing_rect = Signal()
    end_pluspoint_selection = Signal()
    end_minpoint_selection = Signal()
    endDrawing_line_meas = Signal()

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

        self.point_size = 15
        self.text_size = 15

        self.scale_bar_length_mm = 1  # Length of the scale bar in mm
        self.mm_per_pixel = None  # Scale of the image in mm/pixel

        self.setMouseTracking(True)
        self.origin = QPoint()

        self._current_point = None
        self.measure_length = False
        self._current_line = None

        self.pen = QPen()
        self.pen.setStyle(Qt.DashDotLine)
        self.pen.setWidth(4)
        self.pen.setColor(QColor(255, 0, 0, a=255))
        self.pen.setCapStyle(Qt.RoundCap)
        self.pen.setJoinStyle(Qt.RoundJoin)

        self.meas_color = QColor(0, 100, 255, a=255)
        self.pen_yolo = QPen()
        # self.pen.setStyle(Qt.DashDotLine)
        self.pen_yolo.setWidth(2)
        self.pen_yolo.setColor(self.meas_color)
        self.pen_yolo.setCapStyle(Qt.RoundCap)
        self.pen_yolo.setJoinStyle(Qt.RoundJoin)

    def has_photo(self):
        return not self._empty

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
            print('up')
            self.draw_scale_bar(painter)

    def fitInView(self, scale=True):
        rect = QRectF(self._photo.pixmap().rect())
        print(rect)
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
            elif isinstance(item, QGraphicsTextItem):
                self._scene.removeItem(item)
            elif isinstance(item, QGraphicsPolygonItem):
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

    def setPhoto(self, pixmap=None):
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self._photo.setPixmap(pixmap)

            self.point_size = pixmap.width()/100
            self.text_size = pixmap.width()/100
        else:
            self._empty = True
            self.setDragMode(QGraphicsView.NoDrag)
            self._photo.setPixmap(QPixmap())


    def toggleDragMode(self):
        if self.rect or self.select_point:
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            if self.dragMode() == QGraphicsView.ScrollHandDrag:
                self.setDragMode(QGraphicsView.NoDrag)
            elif not self._photo.pixmap().isNull():
                self.setDragMode(QGraphicsView.ScrollHandDrag)


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

    def add_list_infos(self, list_objects, only_name=False):
        for el in list_objects:
            x1, y1, x2, y2, score, class_id = el.yolo_bbox
            text = el.name
            text2 = str(round(el.area, 2)) + 'm² '
            text3 = str(round(el.volume, 2)) + 'm³'

            print(f'adding {text} to viewer')

            # add text 1
            text_item = QGraphicsTextItem()
            text_item.setPos(x1, y1)
            text_item.setHtml(
                "<div style='background-color:rgba(255, 255, 255, 0.3);'>" + text + "</div>")

            self._scene.addItem(text_item)

            if not only_name:
                # add text 2 and 3
                text_item2 = QGraphicsTextItem()
                text_item2.setPos(x1, y2)
                text_item2.setHtml(
                    "<div style='background-color:rgba(255, 255, 255, 0.3);'>" + text2 + "<br>" + text3 + " </div>")
                self._scene.addItem(text_item2)

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

    # mouse events
    def wheelEvent(self, event):
        print(self._zoom)
        if self.has_photo():
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

            self.viewport().update()

    def mousePressEvent(self, event):
        if self.measure_length:
            pass

        else:
            if self._photo.isUnderMouse():
                self.photoClicked.emit(self.mapToScene(event.pos()).toPoint())
        super(PhotoViewer, self).mousePressEvent(event)
