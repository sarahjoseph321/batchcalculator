# controller.py
#
# -*- coding: utf-8 -*-
#
#    Zeolite Batch Calculator
#
# A program for calculating the correct amount of reagents (batch) for a
# particular zeolite composition given by the molar ratio of its components.
#
# The MIT License (MIT)
#
# Copyright (c) 2014 Lukasz Mentel
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import print_function, unicode_literals

import wx
import os
import sys

from collections import OrderedDict

from ObjectListView import ObjectListView
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from batchcalc import dialogs
from batchcalc.model import (Chemical, Component, Electrolyte, Kind, Category,
                             Reaction, PhysicalForm, Batch, Synthesis,
                             SynthesisComponent, SynthesisChemical)

from batchcalc.utils import get_columns, get_resource_path


__version__ = "0.3.1"


#['batches', 'components', 'categories', 'chemicals', 'electrolytes', 'kinds',
# 'reactions', 'physical_forms', 'syntheses']


class Singleton(type):

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class DB(object):
    __metaclass__ = Singleton

    def __init__(self):

        self.session = self.get_session()

    @property
    def dbpath(self):
        '''
        Depending on the execution environment get the proper database path.
        '''

        return get_resource_path('data', 'zeolite.db')

    def get_session(self):
        '''
        When the new database is chosen, close the old session and establish a
        new one.
        '''

        engine = create_engine("sqlite:///{path:s}".format(path=self.dbpath),
                               echo=False)
        Session = sessionmaker(bind=engine, expire_on_commit=False,
                               autoflush=False)
        return Session()

    def switch_session(self, dbpath):

        try:
            self.session.close()
        except:
            pass

        engine = create_engine("sqlite:///{path:s}".format(path=dbpath),
                               echo=False)
        Session = sessionmaker(bind=engine, expire_on_commit=False,
                               autoflush=False)
        self.session = Session()

    def get_batches(self):
        '''
        Return all batch records from the database.
        '''

        return self.session.query(Batch).order_by(Batch.id).all()

    def get_components(self):
        '''
        Return all component records from the database.
        '''

        return self.session.query(Component).order_by(Component.id).all()

    def get_categories(self):
        '''
        Return the list of category records from the database.
        '''

        return self.session.query(Category).order_by(Category.id).all()

    def get_chemicals(self, components=None, showall=False):
        '''
        Return chemicals that are sources for the components present in the
        components list, of the list is empty return all the components.
        '''

        if showall:
            query = self.session.query(Chemical).order_by(Chemical.id).all()
        else:
            compset = set()
            for comp in components:
                temp = self.session.query(Chemical).join(Batch).\
                    filter(Batch.component_id == comp.id).all()
                compset.update(temp)
                query = sorted(list(compset), key=lambda x: x.id)
        return query

    def get_electrolytes(self):
        '''
        Return the list of electrolyte records from the database.
        '''

        return self.session.query(Electrolyte).order_by(Electrolyte.id).all()

    def get_kinds(self):
        '''
        Return the list of kind records from the database.
        '''

        return self.session.query(Kind).order_by(Kind.id).all()

    def get_physical_forms(self):
        '''
        Return the list of physicalform records from the database.
        '''

        return self.session.query(PhysicalForm).order_by(PhysicalForm.id).all()

    def get_reactions(self):
        '''
        Return the list of reaction records from the database.
        '''

        return self.session.query(Reaction).order_by(Reaction.id).all()

    def get_syntheses(self):
        '''
        Return the list of synthesis records from the database.
        '''

        return self.session.query(Synthesis).order_by(Synthesis.id).all()


class ChemicalsDialog(wx.Dialog):

    def __init__(self, parent, model, cols=None, id=wx.ID_ANY,
                 title="", pos=wx.DefaultPosition, size=(850, 520),
                 style=wx.DEFAULT_FRAME_STYLE, name="Chemicals Dialog"):
        '''
        Dialog to select chemicals from the database.

        Args
        ----
        model :
            BatchCalcualtor object instance
        cols : list
            List of OLV ColumnDefn objects with columns to be displayed in the
            dialog
        '''

        dlgwidth = sum([c.minimumWidth for c in cols]) + 60
        super(ChemicalsDialog, self).__init__(parent, id, title, pos,
                                              (dlgwidth, 500), style, name)

        panel = wx.Panel(self)

        self.chem_olv = ObjectListView(panel, wx.ID_ANY,
                                       style=wx.LC_REPORT | wx.SUNKEN_BORDER,
                                       useAlternateBackColors=True)
        self.chem_olv.evenRowsBackColor = "#DCF0C7"
        self.chem_olv.oddRowsBackColor = "#FFFFFF"
        self.chem_olv.cellEditMode = ObjectListView.CELLEDIT_SINGLECLICK

        self.SetChemicals(model, cols)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.chem_olv, proportion=1, flag=wx.EXPAND | wx.ALL,
                       border=5)

        buttonOk = wx.Button(panel, id=wx.ID_OK)
        buttonOk.SetDefault()
        buttonCancel = wx.Button(panel, id=wx.ID_CANCEL)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(buttonCancel, flag=wx.RIGHT, border=10)
        hbox.Add(buttonOk)
        self.sizer.Add(hbox, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

        panel.SetSizerAndFit(self.sizer)

    def SetChemicals(self, model, cols):
        '''Set the columns and object in the OLV and display the result'''

        db = DB()
        self.chem_olv.SetColumns(cols)
        self.chem_olv.CreateCheckStateColumn()
        data = db.get_chemicals(model.components,
                                showall=(len(model.components) == 0))
        for item in data:
            if item.id in [r.id for r in model.chemicals]:
                self.chem_olv.SetCheckState(item, True)
                reac = model.select_item("chemicals", "id", item.id)
                item.mass = reac.mass
                item.concentration = reac.concentration
        self.chem_olv.SetObjects(data)

    def GetCurrentSelections(self):
        '''Return currently selected objects in the dialog.'''

        return self.chem_olv.GetCheckedObjects()


class ComponentsDialog(wx.Dialog):

    def __init__(self, parent, model, cols=None, id=wx.ID_ANY,
                 title="", pos=wx.DefaultPosition, size=(730, 500),
                 style=wx.DEFAULT_FRAME_STYLE, name="Components Dialog"):
        '''
        Dialog to select chemicals from the database.

        Args
        ----
        model :
            BatchCalcualtor object instance
        cols : list
            List of OLV ColumnDefn objects with columns to be displayed in the
            dialog
        '''

        dlgwidth = sum([c.minimumWidth for c in cols]) + 60
        super(ComponentsDialog, self).__init__(parent, id, title, pos,
                                               (dlgwidth, 500), style, name)

        panel = wx.Panel(self)

        self.comp_olv = ObjectListView(panel, wx.ID_ANY,
                                       style=wx.LC_REPORT | wx.SUNKEN_BORDER,
                                       useAlternateBackColors=True)
        self.comp_olv.evenRowsBackColor = "#DCF0C7"
        self.comp_olv.oddRowsBackColor = "#FFFFFF"
        self.comp_olv.CellEditMode = ObjectListView.CELLEDIT_SINGLECLICK

        self.SetComponents(model, cols)

        sizer = wx.FlexGridSizer(rows=2, cols=1, hgap=10, vgap=10)

        sizer.AddGrowableCol(0)
        sizer.AddGrowableRow(0)
        sizer.Add(self.comp_olv,
                  flag=wx.GROW | wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border=5)

        buttonok = wx.Button(panel, id=wx.ID_OK)
        buttonok.SetDefault()
        buttoncancel = wx.Button(panel, id=wx.ID_CANCEL)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(buttoncancel, flag=wx.RIGHT, border=10)
        hbox.Add(buttonok)
        sizer.Add(hbox, flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.RIGHT, border=10)

        panel.SetSizer(sizer)
        panel.Fit()

    def SetComponents(self, model, cols):
        '''Set the columns and object in the OLV and display the result'''

        db = DB()
        self.comp_olv.SetColumns(cols)
        self.comp_olv.CreateCheckStateColumn()
        data = db.get_components()
        for item in data:
            if item.id in [r.id for r in model.components]:
                self.comp_olv.SetCheckState(item, True)
                comp = model.select_item("components", "id", item.id)
                item.moles = comp.moles
        self.comp_olv.SetObjects(data)

    def GetCurrentSelections(self):
        '''Return currently selected objects in the dialog.'''

        return self.comp_olv.GetCheckedObjects()


class AddModifyBatchRecordDialog(wx.Dialog):

    def __init__(self, parent, record=None, title="Add",
                 add_record=True, pos=wx.DefaultPosition, size=(800, 230)):

        super(AddModifyBatchRecordDialog, self).__init__(parent, id=wx.ID_ANY,
            title="{0:s} a Batch Record".format(title), size=size)

        # attributes

        self.db = DB()
        self.record = record
        self.add_record = add_record
        self.panel = wx.Panel(self)

        if record is not None:
            v_coeff = "{0:6.2f}".format(record.coefficient)
        else:
            v_coeff = ""

        font = wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD)

        lbl_title = wx.StaticText(self.panel, -1, "{0:s} Batch Record".format(title))
        lbl_title.SetFont(font)
        lbl_chemical = wx.StaticText(self.panel, -1, "Chemical")
        lbl_component = wx.StaticText(self.panel, -1, "Component")
        lbl_coeff = wx.StaticText(self.panel, -1, "Coefficient")
        lbl_reaction = wx.StaticText(self.panel, -1, "Reaction")

        self.txtc_coeff = wx.TextCtrl(self.panel, -1, value=v_coeff,
                                      size=(50, 20))

        chemicals = self.db.get_chemicals(showall=True)
        components = self.db.get_components()
        reactions = self.db.get_reactions()

        self.chemicals = {i: c for i, c in zip(range(len(chemicals)), chemicals)}
        self.components = {i: c for i, c in zip(range(len(components)), components)}
        self.reactions = {i: c for i, c in zip(range(len(reactions)), reactions)}

        self.ch_chemical = wx.Choice(self.panel, -1, (50, 20), choices=[x.name[:35] for x in chemicals])
        self.ch_component = wx.Choice(self.panel, -1, (50, 20), choices=[x.name[:35] for x in components])
        self.ch_reaction = wx.Choice(self.panel, -1, (50, 20), choices=[x.reaction[:70] for x in reactions])

        if record is not None:
            if self.record.chemical is not None:
                self.ch_chemical.SetStringSelection(self.record.chemical)
            if self.record.component is not None:
                self.ch_component.SetStringSelection(self.record.component)
            if self.record.reaction is not None:
                self.ch_reaction.SetStringSelection(self.record.reaction)

        sizer = wx.GridBagSizer(vgap=5, hgap=5)
        sizer.Add(lbl_title,     pos=(0, 0), span=(1, 3), flag=wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, border=10)
        sizer.Add(lbl_chemical,  pos=(1, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_component, pos=(1, 1), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_coeff,     pos=(1, 2), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_reaction,  pos=(3, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)

        sizer.Add(self.ch_chemical,  pos=(2, 0), span=(1, 1), flag=wx.LEFT|wx.EXPAND|wx.RIGHT, border=10)
        sizer.Add(self.ch_component, pos=(2, 1), span=(1, 1), flag=wx.LEFT|wx.EXPAND|wx.RIGHT, border=10)
        sizer.Add(self.txtc_coeff,   pos=(2, 2), span=(1, 1), flag=wx.LEFT|wx.EXPAND|wx.RIGHT, border=10)
        sizer.Add(self.ch_reaction,  pos=(4, 0), span=(1, 2), flag=wx.LEFT|wx.EXPAND|wx.RIGHT, border=10)

        buttonOk = wx.Button(self.panel, id=wx.ID_ANY, label="{0:s}".format(title))
        buttonOk.SetDefault()
        buttonOk.Bind(wx.EVT_BUTTON, self.OnSaveRecord)
        buttonCancel = wx.Button(self.panel, id=wx.ID_CANCEL)
        buttonCancel.Bind(wx.EVT_BUTTON, self.OnClose)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(buttonOk, flag=wx.RIGHT | wx.LEFT, border=5)
        hbox.Add(buttonCancel, flag=wx.RIGHT | wx.LEFT, border=5)
        sizer.Add(hbox, pos=(5, 0), span=(1, 3),
                  flag=wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM | wx.TOP,
                  border=10)

        sizer.AddGrowableCol(0)
        sizer.AddGrowableCol(1)
        sizer.AddGrowableCol(2)
        self.panel.SetSizerAndFit(sizer)

    def OnSaveRecord(self, event):

        if self.add_record:
            self.add_batch()
        else:
            self.edit_batch()

    def add_batch(self):
        """
        Add a new Batch record to the database.
        """

        data = self.get_data()
        add_batch_record(self.db.session, data)
        dialogs.show_message_dlg("Batch record added", "Success!",
                                 wx.OK | wx.ICON_INFORMATION)

        # clear the TextCtrls to add a new record
        for child in self.panel.GetChildren():
            if isinstance(child, wx.TextCtrl):
                child.SetValue("")
            if isinstance(child, wx.Choice):
                child.SetSelection(-1)

    def edit_batch(self):
        """
        Edit/Modify an existing Batch record in the database.
        """

        data = self.get_data()
        modify_batch_record(self.db.session, self.record.id, data)
        dialogs.show_message_dlg("Batch record modified", "Success!",
                                 wx.OK | wx.ICON_INFORMATION)
        self.Destroy()

    def get_data(self):

        if self.ch_chemical.GetSelection() < 0:
            wx.MessageBox("No Chemical selected", "Error!", style=wx.ICON_ERROR)
            return
        else:
            chemical_id = self.chemicals[self.ch_chemical.GetSelection()].id
        if self.ch_component.GetSelection() < 0:
            wx.MessageBox("No Component selected", "Error!", style=wx.ICON_ERROR)
            return
        else:
            component_id = self.components[self.ch_component.GetSelection()].id

        coefficient = self.txtc_coeff.GetValue()
        if coefficient != "":
            try:
                coefficient = float(coefficient)
            except:
                wx.MessageBox("Coefficient must be a number", "Error!",
                              style=wx.ICON_ERROR)
                self.txtc_coeff.SetBackgroundColour("pink")
                self.txtc_coeff.SetFocus()
                self.txtc_coeff.Refresh()
                return
            self.txtc_coeff.SetBackgroundColour("white")
            self.txtc_coeff.Refresh()
        else:
            wx.MessageBox("No coefficient entered", "Error!",
                          style=wx.ICON_ERROR)
            self.txtc_coeff.SetBackgroundColour("pink")
            self.txtc_coeff.SetFocus()
            self.txtc_coeff.Refresh()
            return

        if self.ch_reaction.GetSelection() < 0:
            reaction_id = None
        else:
            reaction_id = self.reactions[self.ch_reaction.GetSelection()].id

        data = {
            "chemical_id": chemical_id,
            "component_id": component_id,
            "coefficient": coefficient,
            "reaction_id": reaction_id,
        }

        return data

    def OnClose(self, event):
        self.Destroy()


class AddModifyChemicalRecordDialog(wx.Dialog):

    def __init__(self, parent, record=None, title="Add",
                 add_record=True, pos=wx.DefaultPosition, size=(400, 480)):

        super(AddModifyChemicalRecordDialog, self).__init__(parent,
            id=wx.ID_ANY, title="{0:s} a Chemical Record".format(title),
            size=size)

        self.panel = wx.Panel(self)

        # attributes
        self.db = DB()
        self.record = record
        self.add_record = add_record
        if record is not None:
            v_name = record.name
            v_formula = record.formula
            v_molwt = "{0:8.4f}".format(record.molwt)
            v_concentration = "{0:7.3f}".format(record.concentration)
            if record.short_name is not None:
                v_short_name = record.short_name
            else:
                v_short_name = ""
            if record.cas is not None:
                v_cas = record.cas
            else:
                v_cas = ""
            if record.density is not None:
                v_density = "{0:7.3f}".format(record.density)
            else:
                v_density = ""
            if record.pk is not None:
                v_pk = "{0:7.3f}".format(record.pk)
            else:
                v_pk = ""
            if record.smiles is not None:
                v_smiles = record.smiles
            else:
                v_smiles = ""
        else:
            v_name = v_formula = v_molwt = v_short_name = ""
            v_concentration = v_cas = v_density = v_pk = v_smiles = ""

        font = wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD)

        lbl_title = wx.StaticText(self.panel, -1, "{0:s} a Chemical Record".format(title))
        lbl_title.SetFont(font)
        lbl_name = wx.StaticText(self.panel, -1, "Name")
        lbl_formula = wx.StaticText(self.panel, -1, "Formula")
        lbl_molwt = wx.StaticText(self.panel, -1, "Molecular Weight")
        lbl_shname = wx.StaticText(self.panel, -1, "Short Name")
        lbl_conc = wx.StaticText(self.panel, -1, "Concentration")
        lbl_cas = wx.StaticText(self.panel, -1, "CAS")
        lbl_density = wx.StaticText(self.panel, -1, "Density")
        lbl_pk = wx.StaticText(self.panel, -1, "pK")
        lbl_smiles = wx.StaticText(self.panel, -1, "SMILES")
        lbl_kind = wx.StaticText(self.panel, -1, "Kind")
        lbl_form = wx.StaticText(self.panel, -1, "Physical Form")
        lbl_elect = wx.StaticText(self.panel, -1, "Electrolyte")

        self.txtc_name = wx.TextCtrl(self.panel, -1, v_name)
        self.txtc_formula = wx.TextCtrl(self.panel, -1, v_formula)
        self.txtc_molwt = wx.TextCtrl(self.panel, -1, v_molwt, style=wx.TE_RIGHT)
        self.txtc_shname = wx.TextCtrl(self.panel, -1, v_short_name)
        self.txtc_conc = wx.TextCtrl(self.panel, -1, v_concentration)
        self.txtc_cas = wx.TextCtrl(self.panel, -1, v_cas)
        self.txtc_density = wx.TextCtrl(self.panel, -1, v_density)
        self.txtc_pk = wx.TextCtrl(self.panel, -1, v_pk)
        self.txtc_smiles = wx.TextCtrl(self.panel, -1, v_smiles)

        kinds = self.db.get_kinds()
        kind_choices = ["Undefined"] + [x.name for x in kinds]
        forms = self.db.get_physical_forms()
        form_choices = ["Undefined"] + [x.form for x in forms]
        elecs = self.db.get_electrolytes()
        elec_choices = ["Undefined"] + [x.name for x in elecs]

        self.ch_kind = wx.Choice(self.panel, -1, size=(80, -1),
                                 choices=kind_choices)
        self.ch_form = wx.Choice(self.panel, -1, size=(80, -1),
                                 choices=form_choices)
        self.ch_elects = wx.Choice(self.panel, -1, size=(80, -1),
                                   choices=elec_choices)

        if record is not None:
            if self.record.kind is not None:
                self.ch_kind.SetStringSelection(self.record.kind)
            else:
                self.ch_kind.SetSelection(0)
            if self.record.physical_form is not None:
                self.ch_form.SetStringSelection(self.record.physical_form)
            else:
                self.ch_form.SetSelection(0)
            if self.record.electrolyte is not None:
                self.ch_elects.SetStringSelection(self.record.electrolyte)
            else:
                self.ch_elects.SetSelection(0)
        else:
                self.ch_kind.SetSelection(0)
                self.ch_form.SetSelection(0)
                self.ch_elects.SetSelection(0)

        sizer = wx.GridBagSizer(vgap=5, hgap=5)
        sizer.Add(lbl_title,   pos=( 0, 0), span=(1, 2), flag=wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, border=10)
        sizer.Add(lbl_name,    pos=( 1, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_formula, pos=( 2, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_molwt,   pos=( 3, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_shname,  pos=( 4, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_conc,    pos=( 5, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_cas,     pos=( 6, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_density, pos=( 7, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_pk,      pos=( 8, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_smiles,  pos=( 9, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_kind,    pos=(10, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_form,    pos=(11, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)
        sizer.Add(lbl_elect,   pos=(12, 0), span=(1, 1), flag=wx.LEFT|wx.RIGHT, border=10)

        sizer.Add(self.txtc_name,    pos=( 1, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_formula, pos=( 2, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_molwt,   pos=( 3, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_shname,  pos=( 4, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_conc,    pos=( 5, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_cas,     pos=( 6, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_density, pos=( 7, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_pk,      pos=( 8, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_smiles,  pos=( 9, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.ch_kind,      pos=(10, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.ch_form,      pos=(11, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.ch_elects,    pos=(12, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)

        buttonOk = wx.Button(self.panel, id=wx.ID_ANY, label="{0:s}".format(title))
        buttonOk.SetDefault()
        buttonOk.Bind(wx.EVT_BUTTON, self.OnSaveRecord)
        buttonCancel = wx.Button(self.panel, id=wx.ID_CANCEL)
        buttonCancel.Bind(wx.EVT_BUTTON, self.OnClose)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(buttonOk, flag=wx.RIGHT | wx.LEFT, border=5)
        hbox.Add(buttonCancel, flag=wx.RIGHT | wx.LEFT, border=5)
        sizer.Add(hbox, pos=(13, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM | wx.TOP,
                  border=5)

        sizer.AddGrowableCol(1)
        self.panel.SetSizerAndFit(sizer)

    def is_empty(self, textctrl, message):

        if len(textctrl.GetValue()) == 0:
            wx.MessageBox(message, "Error")
            textctrl.SetBackgroundColour("pink")
            textctrl.SetFocus()
            textctrl.Refresh()
            return True
        else:
            textctrl.SetBackgroundColour("white")
            textctrl.Refresh()

    def is_number(self, textctrl, message):

        try:
            float(textctrl.GetValue())
            textctrl.SetBackgroundColour("white")
            textctrl.Refresh()
            return True
        except:
            wx.MessageBox(message, "Error")
            textctrl.SetBackgroundColour("pink")
            textctrl.SetFocus()
            textctrl.Refresh()
            return False

    def add_chemical(self):

        if self.is_empty(self.txtc_name, "Name of the Chemical is required"):
            return

        if self.is_empty(self.txtc_formula, "Formula of the Chemical is required"):
            return

        if self.is_empty(self.txtc_molwt, "Molecular weight of the Chemical is required"):
            return
        else:
            if not self.is_number(self.txtc_molwt, "Molecular weight must be a number"):
                return

        if self.is_empty(self.txtc_conc, "Concentration of the Chemical is required"):
            return
        else:
            if not self.is_number(self.txtc_conc, "Concentration must be a number"):
                return

        if self.txtc_density.GetValue() != "":
            if not self.is_number(self.txtc_density, "Density must be a number"):
                return

        if self.txtc_pk.GetValue() != "":
            if not self.is_number(self.txtc_pk, "pK must be a number"):
                return

        if self.ch_kind.GetStringSelection() == "Undefined":
            wx.MessageBox("Please select the Kind", "Error")
            return

        data = self.get_data()

        add_chemical_record(self.db.session, data)

        dialogs.show_message_dlg("Chemical added", "Success!",
                                 wx.OK | wx.ICON_INFORMATION)

        # clear the TextCtrls to add a new record
        for child in self.panel.GetChildren():
            if isinstance(child, wx.TextCtrl):
                child.SetValue("")
            if isinstance(child, wx.Choice):
                child.SetSelection(0)

    def edit_chemical(self):

        if self.is_empty(self.txtc_name, "Name of the Chemical is required"):
            return

        if self.is_empty(self.txtc_formula, "Formula of the Chemical is required"):
            return

        if self.is_empty(self.txtc_molwt, "Molecular weight of the Chemical is required"):
            return
        else:
            if not self.is_number(self.txtc_molwt, "Molecular weight must be a number"):
                return

        if self.is_empty(self.txtc_conc, "Concentration of the Chemical is required"):
            return
        else:
            if not self.is_number(self.txtc_conc, "Concentration must be a number"):
                return

        if self.ch_kind.GetStringSelection() == "Undefined":
            wx.MessageBox("Please select the Kind", "Error")
            return

        data = self.get_data()
        modify_chemical_record(self.db.session, self.record.id, data)
        self.Destroy()

    def OnSaveRecord(self, event):

        if self.add_record:
            self.add_chemical()
        else:
            self.edit_chemical()

    def OnClose(self, event):
        self.Destroy()

    def get_data(self):
        '''
        Retrieve the data from the dialogs' TextCtrls and ChoiceBoxes
        and return as a dictionary.
        '''

        chem_dict = {
            "name"          : self.txtc_name.GetValue(),
            "formula"       : self.txtc_formula.GetValue(),
            "molwt"         : self.txtc_molwt.GetValue(),
            "short_name"    : self.txtc_shname.GetValue(),
            "concentration" : self.txtc_conc.GetValue(),
            "cas"           : self.txtc_cas.GetValue(),
            "density"       : self.txtc_density.GetValue(),
            "pk"            : self.txtc_pk.GetValue(),
            "smiles"        : self.txtc_smiles.GetValue(),
            "kind"          : self.ch_kind.GetStringSelection(),
            "electrolyte"   : self.ch_elects.GetStringSelection(),
            "physical_form" : self.ch_form.GetStringSelection(),
        }

        return chem_dict


class AddModifyComponentRecordDialog(wx.Dialog):

    def __init__(self, parent, record=None, title="Add",
                 add_record=True, pos=wx.DefaultPosition, size=(400, 270)):

        super(AddModifyComponentRecordDialog, self).__init__(parent,
            id=wx.ID_ANY, title="{0:s} a Component Record".format(title),
            size=size)

        self.panel = wx.Panel(self)

        # attributes
        self.db = DB()
        self.record = record
        self.add_record = add_record
        if record is not None:
            v_name = record.name
            v_formula = record.formula
            v_molwt = "{0:8.4f}".format(record.molwt)
            v_shname = record.short_name
        else:
            v_name = v_formula = v_molwt = v_shname = ""

        font = wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD)

        lbl_title = wx.StaticText(self.panel, -1, "{0:s} Component Record".format(title))
        lbl_title.SetFont(font)
        lbl_name = wx.StaticText(self.panel, -1, "Name")
        lbl_formula = wx.StaticText(self.panel, -1, "Formula")
        lbl_molwt = wx.StaticText(self.panel, -1, "Molecular Weight")
        lbl_shname = wx.StaticText(self.panel, -1, "Short Name")
        lbl_category = wx.StaticText(self.panel, -1, "Category")

        self.txtc_name = wx.TextCtrl(self.panel, -1, v_name)
        self.txtc_formula = wx.TextCtrl(self.panel, -1, v_formula)
        self.txtc_molwt = wx.TextCtrl(self.panel, -1, v_molwt)
        self.txtc_shname = wx.TextCtrl(self.panel, -1, v_shname)

        categ = self.db.get_categories()
        categ_choices = ["Undefined"] + [x.name for x in categ]

        self.ch_category = wx.Choice(self.panel, -1, (100, 50),
                                     choices=categ_choices)

        if record is not None:
            if self.record.category is not None:
                self.ch_category.SetStringSelection(self.record.category)
            else:
                self.ch_category.SetSelection(0)
        else:
            self.ch_category.SetSelection(0)

        sizer = wx.GridBagSizer(vgap=5, hgap=5)
        sizer.Add(lbl_title,    pos=(0, 0), span=(1, 2), flag=wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, border=10)
        sizer.Add(lbl_name,     pos=(1, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT, border=10)
        sizer.Add(lbl_formula,  pos=(2, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT, border=10)
        sizer.Add(lbl_molwt,    pos=(3, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT, border=10)
        sizer.Add(lbl_shname,   pos=(4, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT, border=10)
        sizer.Add(lbl_category, pos=(5, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT, border=10)

        sizer.Add(self.txtc_name,    pos=(1, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_formula, pos=(2, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_molwt,   pos=(3, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.txtc_shname,  pos=(4, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)
        sizer.Add(self.ch_category,  pos=(5, 1), span=(1, 1), flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)

        buttonOk = wx.Button(self.panel, id=wx.ID_ANY, label="{0:s}".format(title))
        buttonOk.SetDefault()
        buttonOk.Bind(wx.EVT_BUTTON, self.OnSaveRecord)
        buttonCancel = wx.Button(self.panel, id=wx.ID_CANCEL)
        buttonCancel.Bind(wx.EVT_BUTTON, self.OnClose)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(buttonOk, flag=wx.RIGHT | wx.LEFT, border=5)
        hbox.Add(buttonCancel, flag=wx.RIGHT | wx.LEFT, border=5)
        sizer.Add(hbox, pos=(6, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM | wx.TOP,
                  border=5)

        sizer.AddGrowableCol(1)
        self.panel.SetSizerAndFit(sizer)

    def is_empty(self, textctrl, message):

        if len(textctrl.GetValue()) == 0:
            wx.MessageBox(message, "Error")
            textctrl.SetBackgroundColour("pink")
            textctrl.SetFocus()
            textctrl.Refresh()
            return True
        else:
            textctrl.SetBackgroundColour("white")
            textctrl.Refresh()

    def is_number(self, textctrl, message):

        try:
            float(textctrl.GetValue())
            textctrl.SetBackgroundColour("white")
            textctrl.Refresh()
            return True
        except:
            wx.MessageBox(message, "Error")
            textctrl.SetBackgroundColour("pink")
            textctrl.SetFocus()
            textctrl.Refresh()
            return False

    def OnSaveRecord(self, event):

        if self.add_record:
            self.add_component()
        else:
            self.edit_component()

    def add_component(self):

        if self.is_empty(self.txtc_name, "Name of the Component is required"):
            return

        if self.is_empty(self.txtc_formula, "Formula of the Component is required"):
            return

        if self.is_empty(self.txtc_molwt, "Molecular weight of the Component is required"):
            return
        else:
            if not self.is_number(self.txtc_molwt, "Molecular weight must be a number"):
                return

        if self.ch_category.GetStringSelection() == "Undefined":
            wx.MessageBox("Please select the Category", "Error")
            return

        data = self.get_data()

        add_component_record(self.db.session, data)

        dialogs.show_message_dlg("Component added", "Success!",
                                 wx.OK | wx.ICON_INFORMATION)

        # clear the TextCtrls to add a new record
        for child in self.panel.GetChildren():
            if isinstance(child, wx.TextCtrl):
                child.SetValue("")
            if isinstance(child, wx.Choice):
                child.SetSelection(0)

    def edit_component(self):

        if self.is_empty(self.txtc_name, "Name of the Component is required"):
            return

        if self.is_empty(self.txtc_formula, "Formula of the Component is required"):
            return

        if self.is_empty(self.txtc_molwt, "Molecular weight of the Component is required"):
            return
        else:
            if not self.is_number(self.txtc_molwt, "Molecular weight must be a number"):
                return

        if self.ch_category.GetStringSelection() == "Undefined":
            wx.MessageBox("Please select the Category", "Error")
            return

        data = self.get_data()

        modify_component_record(self.db.session, self.record.id, data)
        dialogs.show_message_dlg("Component modified", "Success!",
                                 wx.OK | wx.ICON_INFORMATION)

        self.Destroy()

    def OnClose(self, event):
        self.Destroy()

    def get_data(self):

        comp_dict = {
            "name": self.txtc_name.GetValue(),
            "formula": self.txtc_formula.GetValue(),
            "molwt": self.txtc_molwt.GetValue(),
            "short_name": self.txtc_shname.GetValue(),
            "category": self.ch_category.GetStringSelection(),
        }

        return comp_dict


SYNTH_FIELDS = OrderedDict([
    ("name", {"label": "Name", "required": True}),
    ("target_material", {"label": "Target Material", "required": False}),
    ("laborant", {"label": "Laborant", "required": True}),
    ("reference", {"label": "Reference", "required": False}),
    ("temperature", {"label": "Temperature in [K]", "required": False}),
    ("crystallization_time", {"label": "Crystallization Time [h]", "required": False}),
    ("stirring", {"label": "Stirring", "required": False}),
    ("description", {"label": "Description", "required": True}),
])


class AddModifySynthesisRecordDialog(wx.Dialog):

    def __init__(self, parent, model, record=None, title="Add",
                 add_record=True, pos=wx.DefaultPosition, size=(500, 670)):

        super(AddModifySynthesisRecordDialog, self).__init__(parent,
            id=wx.ID_ANY, title="{0:s} a Synthesis Record".format(title),
            size=size)

        # Attributes

        self.model = model
        self.record = record
        self.add_record = add_record
        self.title = title
        self.panel = wx.Panel(self)

        self.synth = SYNTH_FIELDS

        self.comp_cols = ["name", "formula", "molwt", "short", "category"]
        self.chem_cols = ["name", "formula", "conc", "molwt", "short", "kind",
                          "physform", "cas"]

        comptxt = wx.StaticText(self.panel, -1, label="Components")
        chemtxt = wx.StaticText(self.panel, -1, label="Chemicals")
        comptxt.SetFont(wx.Font(12, wx.SWISS, wx.NORMAL, wx.BOLD))
        chemtxt.SetFont(wx.Font(12, wx.SWISS, wx.NORMAL, wx.BOLD))

        self.comp_olv = ObjectListView(self.panel, wx.ID_ANY, size=(-1, 200),
                                       style=wx.LC_REPORT | wx.SUNKEN_BORDER,
                                       useAlternateBackColors=True)
        self.comp_olv.evenRowsBackColor = "#DCF0C7"
        self.comp_olv.oddRowsBackColor = "#FFFFFF"
        self.comp_olv.cellEditMode = ObjectListView.CELLEDIT_DOUBLECLICK

        self.chem_olv = ObjectListView(self.panel, wx.ID_ANY,
                                       style=wx.LC_REPORT | wx.SUNKEN_BORDER,
                                       useAlternateBackColors=True)
        self.chem_olv.evenRowsBackColor = "#DCF0C7"
        self.chem_olv.oddRowsBackColor = "#FFFFFF"
        self.chem_olv.cellEditMode = ObjectListView.CELLEDIT_DOUBLECLICK

        self.SetComponents()
        self.SetChemicals()

        gbs = wx.GridBagSizer(vgap=5, hgap=5)
        gbs.Add(comptxt, pos=(0, 0), span=(1, 1),
                flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.ALIGN_CENTER_HORIZONTAL,
                border=10)
        gbs.Add(chemtxt, pos=(0, 1), span=(1, 1),
                flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.ALIGN_CENTER_HORIZONTAL,
                border=10)
        gbs.Add(self.comp_olv, pos=(1, 0), span=(2, 1),
                flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND,
                border=10)
        gbs.Add(self.chem_olv, pos=(1, 1), span=(2, 1),
                flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND,
                border=10)
        gbs.AddGrowableCol(0)
        gbs.AddGrowableCol(1)

        if record is not None:
            for attr in self.synth.keys():
                if getattr(record, attr) is not None:
                    if attr in ["temperature", "crystallization_time"]:
                        self.synth[attr]["value"] = "{0:7.3f}".format(getattr(record, attr))
                    elif attr == "id":
                        self.synth[attr]["value"] = "{0:d}".format(getattr(record, attr))
                    else:
                        self.synth[attr]["value"] = getattr(record, attr)
                else:
                    self.synth[attr]["value"] = ""
        else:
            for attr in self.synth.keys():
                self.synth[attr]["value"] = ""

        font = wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD)

        lbl_title = wx.StaticText(self.panel, -1,
                                  "{0:s} a Synthesis Record".format(title))
        lbl_title.SetFont(font)

        for attr in self.synth.keys():
            self.synth[attr]["sttext"] = wx.StaticText(self.panel, -1,
                                                       self.synth[attr]["label"])
            if attr == "description":
                self.synth[attr]["txtctrl"] = wx.TextCtrl(self.panel, -1,
                                                value=self.synth[attr]["value"],
                                                size=(-1, 100),
                                                style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER)
            else:
                self.synth[attr]["txtctrl"] = wx.TextCtrl(self.panel, -1,
                                                value=self.synth[attr]["value"])

        # create and populate sizer for the text controls

        txtsizer = wx.GridBagSizer(vgap=5, hgap=5)
        txtsizer.Add(lbl_title, pos=(0, 0), span=(1, 2),
                     flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=10)

        for i, attr in enumerate(self.synth.keys(), start=1):
            txtsizer.Add(self.synth[attr]["sttext"], pos=(i, 0), span=(1, 1),
                         flag=wx.LEFT | wx.RIGHT, border=10)
            txtsizer.Add(self.synth[attr]["txtctrl"], pos=(i, 1), span=(1, 1),
                         flag=wx.LEFT | wx.EXPAND | wx.RIGHT, border=10)

        txtsizer.AddGrowableCol(1)

        buttonOk = wx.Button(self.panel, id=wx.ID_ANY, label="{0:s}".format(title))
        buttonOk.SetDefault()
        buttonOk.Bind(wx.EVT_BUTTON, self.OnSaveRecord)
        buttonCancel = wx.Button(self.panel, id=wx.ID_CANCEL)
        buttonCancel.Bind(wx.EVT_BUTTON, self.OnClose)

        btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        btnsizer.Add(buttonOk, flag=wx.RIGHT | wx.LEFT, border=5)
        btnsizer.Add(buttonCancel, flag=wx.RIGHT | wx.LEFT, border=5)

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(txtsizer, flag=wx.RIGHT | wx.LEFT | wx.GROW, border=5)
        mainsizer.Add(gbs,
                      flag=wx.RIGHT | wx.LEFT | wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL,
                      border=5)
        mainsizer.Add(btnsizer,
                      flag=wx.RIGHT | wx.LEFT | wx.TOP | wx.ALIGN_CENTER_HORIZONTAL,
                      border=10)

        self.panel.SetSizerAndFit(mainsizer)

    def is_empty(self, textctrl, message):

        if len(textctrl.GetValue()) == 0:
            wx.MessageBox(message, "Error")
            textctrl.SetBackgroundColour("pink")
            textctrl.SetFocus()
            textctrl.Refresh()
            return True
        else:
            textctrl.SetBackgroundColour("white")
            textctrl.Refresh()

    def is_number(self, textctrl, message):
        '''
        Check if the string entered in the `textctrl` can be converted to
        float. Return True if it can otherwise change the `textctrl` color,
        show a dialog with the `message` and return False.
        '''

        try:
            float(textctrl.GetValue())
            textctrl.SetBackgroundColour("white")
            textctrl.Refresh()
            return True
        except:
            wx.MessageBox(message, "Error")
            textctrl.SetBackgroundColour("pink")
            textctrl.SetFocus()
            textctrl.Refresh()
            return False

    def SetComponents(self):

        olv_cols = get_columns(["label", "moles"])
        self.comp_olv.SetColumns(olv_cols)

        if self.add_record:
            self.comp_olv.SetObjects(self.model.components)
        else:
            if self.record is not None:
                components = [c.component for c in self.record.components]
                for comp, synthcomp in zip(components, self.record.components):
                    comp.moles = synthcomp.moles
                self.comp_olv.SetObjects(components)
            else:
                self.comp_olv.SetObjects([])

    def SetChemicals(self):

        olv_cols = get_columns(["label", "mass"])
        self.chem_olv.SetColumns(olv_cols)

        if self.add_record:
            self.chem_olv.SetObjects(self.model.chemicals)
        else:
            if self.record is not None:
                chemicals = [c.chemical for c in self.record.chemicals]
                for chem, synthchem in zip(chemicals, self.record.chemicals):
                    chem.mass = synthchem.mass
                self.chem_olv.SetObjects(chemicals)
            else:
                self.comp_olv.SetObjects([])

    def textctrls_correct(self):
        '''
        Check if the data is typed correctly into the TextCtrls
        '''

        for k, v in self.synth.items():
            if v["required"]:
                if self.is_empty(v["txtctrl"],
                                 "{} is required".format(v["label"])):
                    return False
                elif k in ["temperature", "crystallization_time"]:
                    if not self.is_number(v["txtctrl"],
                                          "{} must be a number".format(v["label"])):
                        return False
        return True

    def add_synthesis(self):
        '''
        Retrieve the values entered in the dialog and insert a record to the db
        and commit.
        '''

        db = DB()

        if not self.textctrls_correct():
            return

        data = self.get_textctrl_data()
        data.update(self.get_model_data())

        add_synthesis_record(db.session, data)

        dialogs.show_message_dlg("Synthesis added", "Success!",
                                 wx.OK | wx.ICON_INFORMATION)

        # clear the TextCtrls to add a new record
        for child in self.panel.GetChildren():
            if isinstance(child, wx.TextCtrl):
                child.SetValue("")
        self.model.reset()
        self.comp_olv.SetObjects([])
        self.chem_olv.SetObjects([])

        self.Destroy()

    def edit_synthesis(self):
        '''
        Get the values entered in the dialog and insert a record to the db and
        commit.
        '''

        db = DB()

        if not self.textctrls_correct():
            return

        data = self.get_textctrl_data()

        modify_synthesis_record(db.session, self.record.id, data)

        dialogs.show_message_dlg("Synthesis modified", "Success!",
                                 wx.OK | wx.ICON_INFORMATION)

        self.Destroy()

    def OnSaveRecord(self, event):

        if self.add_record:
            self.add_synthesis()
        else:
            self.edit_synthesis()

    def OnClose(self, event):
        '''Close the dialog'''

        self.Destroy()

    def get_textctrl_data(self):
        '''
        Retrieve the data from the dialogs' TextCtrls and ChoiceBoxes
        and return as a dictionary.
        '''

        data = {}
        for k, v in self.synth.items():
            data[k] = v['txtctrl'].GetValue()

        for item in ["temperature", "crystallization_time"]:
            try:
                data[item] = float(data[item])
            except:
                data[item] = None

        return data

    def get_model_data(self):
        '''
        Retrieve the data from the model
        and return as a dictionary.
        '''

        data = {'components': [], 'chemicals': []}
        for component in self.model.components:
            data['components'].append(SynthesisComponent(component_id=component.id,
                                                         component=component,
                                                         moles=component.moles))
        for chemical in self.model.chemicals:
            data['chemicals'].append(SynthesisChemical(chemical_id=chemical.id,
                                                       chemical=chemical,
                                                       mass=chemical.mass))

        return data


def print_attrs(inst):

    print("Class {0}".format(inst.__class__.__name__))
    for key in sorted(inst.__dict__.keys()):
        if not key.startswith("_"):
            print("{0:s} : {1:s}".format(key, str(getattr(inst, key))))


################################################################################
# controller methods
################################################################################

# Batch controller methods


def add_batch_record(session, data):
    """
    Add a Batch record to the database, the data should be in the form of
    a dictionary:

    data = {'chemical_id' : '1', 'component_id' : '1', 'coefficient' : 0.5,
            'reaction_id' : 3,}
    """

    batch = Batch(**data)
    session.add(batch)
    session.commit()


def delete_batch_record(session, id_num):
    """
    Delete an exisitng Batch record.
    """

    batch = session.query(Batch).get(id_num)
    session.delete(batch)
    session.commit()


def modify_batch_record(session, id_num, data):
    """
    Edit/Modify an existing Batch record.
    """

    batch = session.query(Batch).get(id_num)
    batch.coefficient = data['coefficient']
    if data['chemical_id'] is not None:
        batch._chemical = session.query(Chemical).get(data['chemical_id'])
    if data['component_id'] is not None:
        batch._component = session.query(Component).get(data['component_id'])
    if data['reaction_id'] is not None:
        batch._reaction = session.query(Reaction).get(data['reaction_id'])
    session.add(batch)
    session.commit()


# Chemical controller methods


def add_chemical_record(session, data):
    """
    Add a Chemical record to the database, the data should be in the form of
    a dictionary:

    data = {'name' : 'water', 'formula' : 'H2O', 'molwt' : 18.0152,
            '_kind_id' : 3, 'concentration' : 1.0, 'cas' : '7732-18-5',
            '_physical_form_id' : 3, 'density' : 0.997}
    """

    kind = data.pop("kind", None)
    electrolyte = data.pop("electrolyte", None)
    if electrolyte == "Undefined":
        electrolyte = None
    physical_form = data.pop("physical_form", None)
    if physical_form == "Undefined":
        physical_form = None

    for k, v in data.items():
        if v == "":
            data[k] = None

    chemical = Chemical(**data)
    chemical._kind = session.query(Kind).filter(Kind.name == kind).one()

    if physical_form is not None:
        chemical._physical_form = session.query(PhysicalForm).filter(PhysicalForm.form == physical_form).one()

    if electrolyte is not None:
        chemical._electrolyte = session.query(Electrolyte).filter(Electrolyte.name == electrolyte).one()

    session.add(chemical)
    session.commit()


def delete_chemical_record(session, id_num):
    """
    Delete a Chemical record.
    """

    chemical = session.query(Chemical).get(id_num)
    session.delete(chemical)
    session.commit()


def modify_chemical_record(session, id_num, data):
    """
    Edit/Modify Chemical record in the database,
    """

    kind = data.pop("kind", None)
    electrolyte = data.pop("electrolyte", None)
    if electrolyte == "Undefined":
        electrolyte = None
    physical_form = data.pop("physical_form", None)
    if physical_form == "Undefined":
        physical_form = None

    chemical = session.query(Chemical).get(id_num)

    for k, v in data.items():
        if v == "":
            data[k] = None
        setattr(chemical, k, data[k])

    chemical._kind = session.query(Kind).filter(Kind.name == kind).one()

    if physical_form is not None:
        chemical._physical_form = session.query(PhysicalForm).filter(PhysicalForm.form == physical_form).one()

    if electrolyte is not None:
        chemical._electrolyte = session.query(Electrolyte).filter(Electrolyte.name == electrolyte).one()

    session.add(chemical)
    session.commit()


# Compoment controller methods


def add_component_record(session, data):
    """
    Add a Component record to the database, the data should be in the form of
    a dictionary:

    data = {'name' : 'water', 'formula' : 'H2O', 'molwt' : 18.0152,
            '_catgory_id' : 3, 'short_name' : ''}
    """

    category = data.pop("category", None)
    if category == "Undefined":
        category = None

    component = Component(**data)

    if category is not None:
        component._category = session.query(Category).filter(Category.name == category).one()

    session.add(component)
    session.commit()


def delete_component_record(session, id_num):
    """
    Delete a Component record.
    """

    component = session.query(Component).get(id_num)
    session.delete(component)
    session.commit()


def modify_component_record(session, id_num, data):
    """
    Edit/Modify Component record in the database,
    """

    category = data.pop("category", None)
    if category == "Undefined":
        category = None

    component = session.query(Component).get(id_num)

    for k in data.keys():
        setattr(component, k, data[k])

    if category is not None:
        component._category = session.query(Category).filter(Category.name == category).one()

    session.add(component)
    session.commit()


# Reaction controller methods


def add_reaction_record(session, data):

    reaction = Reaction(reaction=data)
    session.add(reaction)
    session.commit()


def delete_reaction_record(session, id_num):
    """
    Delete a Reaction record.
    """

    reaction = session.query(Reaction).get(id_num)
    session.delete(reaction)
    session.commit()


def modify_reaction_record(session, id_num, data):
    """
    Modify/Edit an existing Reaction record in the database
    """

    reaction = session.query(Reaction).get(id_num)
    reaction.reaction = data
    session.add(reaction)
    session.commit()


# Category controller methods


def add_category_record(session, data):

    category = Category(name=data)
    session.add(category)
    session.commit()


def delete_category_record(session, id_num):
    """
    Delete a category record.
    """

    category = session.query(Category).get(id_num)
    session.delete(category)
    session.commit()


def modify_category_record(session, id_num, data):
    """
    Modify/Edit an existing Category record in the database
    """

    category = session.query(Category).get(id_num)
    category.name = data
    session.add(category)
    session.commit()


# Kinds controller methods


def fill_kinds_table(session):
    """
    Fill the kinds table with allowed values
    """

    kinds = ["mixture", "solution", "reactant"]

    for kind in kinds:
        add_kind_record(session, kind)


def add_kind_record(session, data):
    """
    Add a Kind record.
    """

    kind = Kind(name=data)
    session.add(kind)
    session.commit()


def delete_kind_record(session, id_num):
    """
    Delete a Kind record.
    """

    kind = session.query(Kind).get(id_num)
    session.delete(kind)
    session.commit()


def modify_kind_record(session, id_num, data):
    """
    Modify/Edit an existing Kind record in the database
    """

    kind = session.query(Kind).get(id_num)
    kind.name = data
    session.add(kind)
    session.commit()


# Physical_forms controller methods


def fill_physical_forms_table(session):
    """
    Fill the physical_forms table with allowed values
    """

    phfs = ["crystals", "solid", "liquid", "gas"]

    for phf in phfs:
        add_physical_form_record(session, phf)


def add_physical_form_record(session, data):
    """
    Add a PhysicalForm record.
    """

    phf = PhysicalForm(form=data)
    session.add(phf)
    session.commit()


def delete_physical_form_record(session, id_num):
    """
    Delete a PhysicalForm record.
    """

    phf = session.query(PhysicalForm).get(id_num)
    session.delete(phf)
    session.commit()


def modify_physical_form_record(session, id_num, data):
    """
    Modify/Edit an existing PhysicalForm record in the database
    """

    phf = session.query(PhysicalForm).get(id_num)
    phf.form = data
    session.add(phf)
    session.commit()


# Electrolyte controller methods


def fill_electrolytes_table(session):
    """
    Fill the electrolyte table with allowed values
    """

    elecs = ["nonelectrolyte", "strong acid", "strong base", "weak acid",
             "weak base"]

    for elec in elecs:
        add_electrolyte_record(session, elec)


def add_electrolyte_record(session, data):
    """
    Add a Electrolyte record.
    """

    elec = Electrolyte(name=data)
    session.add(elec)
    session.commit()


def delete_electrolyte_record(session, id_num):
    """
    Delete a Electrolyte record.
    """

    elec = session.query(Electrolyte).get(id_num)
    session.delete(elec)
    session.commit()


def modify_electrolyte_record(session, id_num, data):
    """
    Modify/Edit an existing Electrolyte record in the database
    """

    elec = session.query(Electrolyte).get(id_num)
    elec.name = data
    session.add(elec)
    session.commit()


# Synthesis controller methods


def add_synthesis_record(session, data):
    """
    Add a Synthesis record.
    """

    synth = Synthesis(**data)
    if 'chemicals' in data.keys():
        synth.chemicals = data['chemicals']
    if 'components' in data.keys():
        synth.components = data['components']
    session.add(synth)
    session.commit()


def modify_synthesis_record(session, id_num, data):
    """
    Modify/Edit an existing Synthesis record in the database
    """

    synth = session.query(Synthesis).get(id_num)

    for k in data.keys():
        setattr(synth, k, data[k])

    session.add(synth)
    session.commit()


def delete_synthesis_record(session, id_num):
    """
    Delete a Synthesis record.
    """

    synth = session.query(Synthesis).get(id_num)
    session.delete(synth)
    session.commit()
