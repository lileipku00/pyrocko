import operator
from itertools import groupby
from PyQt4.QtCore import *  # noqa
from PyQt4.QtGui import *  # noqa

from pyrocko.gui_util import EventMarker, PhaseMarker, Marker
from pyrocko import util

_header_data = ['Type', 'Time', 'Magnitude']
_column_mapping = dict(zip(_header_data, range(len(_header_data))))
_attr_mapping = dict(zip([0,1,2], ['__class__', 'tmin', 'magnitude']))

class MarkerItemDelegate(QStyledItemDelegate):
    """Takes are of the table's style."""
    def __init__(self, *args, **kwargs):
        QStyledItemDelegate.__init__(self, *args, **kwargs)

    def initStyleOption(self, option, index):
        if not index.isValid():
            return
        QStyledItemDelegate.initStyleOption(self, option, index)
        if index.row()%2==0:
            option.backgroundBrush = QBrush(QColor(50,10,10,30))

class MarkerSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        QSortFilterProxyModel.__init__(self)

class MarkerTableView(QTableView):
    def __init__(self, *args, **kwargs):
        QTableView.__init__(self, *args, **kwargs)

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)

        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.viewer = None

    def keyPressEvent(self, key_event):
        keytext = str(key_event.text())
        self.viewer.keyPressEvent(key_event)

    def resizeEvent(self, event):
        width = event.size().width()
        self.setColumnWidth(_column_mapping['Type'], width*0.1)
        self.setColumnWidth(_column_mapping['Time'], width*0.7)
        self.setColumnWidth(_column_mapping['Magnitude'], width*0.2)

    def set_viewer(self, viewer):
        self.viewer = viewer


class MarkerTableModel(QAbstractTableModel):
    def __init__(self, *args, **kwargs):
        QAbstractTableModel.__init__(self, *args, **kwargs)
        self.viewer = None
        self.headerdata = _header_data

    def set_viewer(self, viewer):
        self.viewer = viewer
        self.connect(self.viewer, SIGNAL('markers_added(int,int)'), self.markers_added)
        self.connect(self.viewer, SIGNAL('markers_removed(QList<int>)'), self.markers_removed)
        
    def rowCount(self, parent):
        if not self.viewer:
            return 0
        return len(self.viewer.markers)

    def columnCount(self, parent):
        return len(_column_mapping)

    def markers_added(self, istart, istop):
        """Insert rows representing a :py:class:`Marker` in the :py:class:`MarkerTableModel`."""
        self.emit(SIGNAL('dataChanged'))
        self.beginInsertRows(QModelIndex(), istart, istop)
        self.endInsertRows()
        #self.emit(SIGNAL('dataChanged()'))

    def make_chunks(self, items):
        """Split a list of integers into sublists of consecutive elements."""
        return [map(operator.itemgetter(1), g) for k, g in groupby(enumerate(items), lambda (i,x):i-x)]

    def markers_removed(self, iremove):
        """Remove rows representing a :py:class:`Marker` from the :py:class:`MarkerTableModel`."""
        if len(iremove) == 0:
            return
        for chunk in self.make_chunks(iremove):
            self.beginRemoveRows(QModelIndex(), min(chunk), max(chunk))
        self.endRemoveRows()

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return QVariant(self.headerdata[col])
            elif role == Qt.SizeHintRole:
                return QSize(10,20)
        else:
            return QVariant()

    def data(self, index, role):
        if not self.viewer:
            return QVariant()
        if role == Qt.DisplayRole:
            imarker = index.row()
            marker = self.viewer.markers[imarker]
            if index.column() == _column_mapping['Type']:
                if isinstance(marker, EventMarker):
                    s = 'E'
                elif isinstance(marker, PhaseMarker):
                    s = 'P'
                else:
                    s = ''

            if index.column() == _column_mapping['Time']:
                s = util.time_to_str(marker.tmin)


            if index.column() == _column_mapping['Magnitude']:
                if isinstance(marker, EventMarker):
                    s = str(marker.get_event().magnitude)
                else:
                    s = ''

            return QVariant(QString(s))

        return QVariant()

    def setData(self, index, value, role):
        """
        """
        if role == Qt.EditRole:
            imarker = index.row()
            marker = self.viewer.markers[imarker]
            if index.column() == 2 and isinstance(marker, EventMarker):
                marker.get_event().magnitude = value.toFloat()[0]
                self.emit(SIGNAL('dataChanged()'))
            return True
        return False

    def flags(self, index):
        if index.column() == _column_mapping['Magnitude'] and isinstance(self.viewer.markers[index.row()], EventMarker):
            return Qt.ItemFlags(35)
        return Qt.ItemFlags(33)

class MarkerEditor(QTableWidget):
    def __init__(self, *args, **kwargs):
        QTableWidget.__init__(self, *args, **kwargs)

        layout = QGridLayout()
        self.setLayout(layout)
        self.marker_table = MarkerTableView()
        #self.marker_table.setItemDelegate(MarkerItemDelegate(self.marker_table))

        self.marker_model = MarkerTableModel()
        self.proxy_filter = MarkerSortFilterProxyModel()
        self.proxy_filter.setDynamicSortFilter(True)
        self.proxy_filter.setSourceModel(self.marker_model)

        header = self.marker_table.horizontalHeader()
        header.setModel(self.marker_model)
        self.marker_table.setModel(self.proxy_filter)

        self.selection_model = QItemSelectionModel(self.proxy_filter)
        self.marker_table.setSelectionModel(self.selection_model)
        self.connect(
            self.selection_model,
            SIGNAL("selectionChanged(QItemSelection, QItemSelection)"),
            self.set_selected_markers)

        layout.addWidget(self.marker_table, 0, 0)
        self.viewer = None

    def set_viewer(self, viewer):
        self.marker_model.set_viewer(viewer)
        self.viewer = viewer
        self.connect(self.viewer, SIGNAL('changed_marker_selection'), self.update_selection_model)
        #self.connect(self.marker_table, SIGNAL("cellDoubleClicked(int, int)"), self.show_details)

        self.marker_table.set_viewer(self.viewer)

    def set_selected_markers(self, selected, deselected):
        ''' set markers selected in viewer at selection in table.'''
        selected_markers = [self.viewer.markers[self.proxy_filter.mapToSource(i).row()] for i in self.selection_model.selectedRows()]
        self.viewer.set_selected_markers(selected_markers)

    def get_marker_model(self):
        '''Return :py:class:`MarkerTableModel` instance'''
        return self.marker_model

    def update_selection_model(self, indices):
        ''' :param indices: list of indices of selected markers.'''
        self.selection_model.clearSelection()
        num_columns = len(_header_data)
        flag = QItemSelectionModel.SelectionFlags(2)
        selections = QItemSelection()
        for i in indices:
            left = self.proxy_filter.mapFromSource(self.marker_model.index(i, 0))
            right = self.proxy_filter.mapFromSource(self.marker_model.index(i, num_columns-1))
            row_selection = QItemSelection(left, right)
            row_selection.select(left, right)
            selections.merge(row_selection, flag)
        self.selection_model.select(selections, flag)
        if len(indices)!=0:
            self.marker_table.scrollTo(self.proxy_filter.mapFromSource(self.marker_model.index(indices[0],0)))

    def show_details(self):
        print 'show details'
