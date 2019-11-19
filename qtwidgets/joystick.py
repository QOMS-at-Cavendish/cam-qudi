from qtpy import QtCore, QtGui, QtWidgets

class Joystick(QtWidgets.QWidget):
    """
    Custom xy joystick widget.

    Public methods:
    joystickDirection() - get tuple (angle, distance) of current position

    Signal moved(tuple pos) - emitted when joystick is moved. 
            pos: Position in circular coordinates (angle, distance)
    """

    moved = QtCore.Signal(tuple)

    def __init__(self, parent=None):
        super(Joystick, self).__init__(parent)
        self.setMinimumSize(100, 100)
        self.movingOffset = QtCore.QPointF(0, 0)
        self.grabCenter = False
        self.__maxDistance = 40

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        bounds = QtCore.QRectF(-self.__maxDistance, -self.__maxDistance, self.__maxDistance * 2, self.__maxDistance * 2).translated(self._center())
        painter.drawEllipse(bounds)
        painter.setBrush(QtGui.QColor('#AAAAAA'))
        if self.grabCenter:
            painter.drawLine(self._center(), self.movingOffset)
        painter.drawEllipse(self._centerEllipse())

    def _centerEllipse(self):
        if self.grabCenter:
            return QtCore.QRectF(-5, -5, 10, 10).translated(self.movingOffset)
        return QtCore.QRectF(-5, -5, 10, 10).translated(self._center())

    def _center(self):
        return QtCore.QPointF(self.width()/2, self.height()/2)


    def _boundJoystick(self, point):
        limitLine = QtCore.QLineF(self._center(), point)
        if (limitLine.length() > self.__maxDistance):
            limitLine.setLength(self.__maxDistance)
        return limitLine.p2()

    def joystickDirection(self):
        if not self.grabCenter:
            return (0, 0)
        normVector = QtCore.QLineF(self._center(), self.movingOffset)
        currentDistance = normVector.length()
        angle = normVector.angle()

        distance = min(currentDistance / self.__maxDistance, 1.0)

        return (angle, distance)

    def mousePressEvent(self, ev):
        #self.grabCenter = self._centerEllipse().contains(ev.pos())
        self.grabCenter = True
        self.mouseMoveEvent(ev)
        return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, event):
        self.grabCenter = False
        self.movingOffset = QtCore.QPointF(0, 0)
        self.update()
        self.moved.emit((0,0))

    def mouseMoveEvent(self, event):
        if self.grabCenter:
            self.movingOffset = self._boundJoystick(event.pos())
            self.update()
            self.moved.emit(self.joystickDirection())