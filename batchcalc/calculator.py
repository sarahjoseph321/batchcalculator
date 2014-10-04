# -*- coding: utf-8 -*-
#
#    Zeolite Batch Calculator
#
# A program based for calculating the correct amount of reagents (batch) for a
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

__version__ = "0.1.0"

import operator
import os
import pkg_resources
import re

from numpy.linalg import solve
import numpy as np

from sqlalchemy import Column, Integer, String, Float, create_engine, ForeignKey
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

_minwidth = 15

Base = declarative_base()

class Category(Base):
    __tablename__ = 'categories'

    id        = Column(Integer, primary_key=True)
    name      = Column(String)
    full_name = Column(String)

    def __repr__(self):
        return "<Category(id={i}, name={n}, full_name={f})>".format(i=self.id,
                n=self.name, f=self.full_name)

class Types(Base):
    __tablename__ = 'types'

    id   = Column(Integer, primary_key=True)
    name = Column(String)

    def __repr__(self):
        return "<Types(id={i}, name={n})>".format(i=self.id, n=self.name)

class Reaction(Base):
    __tablename__ = 'reactions'

    id       = Column(Integer, primary_key=True)
    reaction = Column(String)

    def __repr__(self):
        return "<Reaction(id={i}, reaction={n})>".format(i=self.id, n=self.reaction)

class Batch(Base):
    __tablename__ = 'batch'

    id           = Column(Integer, primary_key=True)
    reactant_id  = Column(Integer, ForeignKey('chemicals.id'), nullable=False)
    component_id = Column(Integer, ForeignKey('components.id'), nullable=False)
    reaction_id  = Column(Integer, ForeignKey('reactions.id'), nullable=True)
    coefficient  = Column(Float, nullable=True)

    def __repr__(self):
        return "<Batch(id={i:>2d}, reactant_id='{n:>5d}', component_id='{z:>5d}', coefficient={c:8.2f})>".format(
                i=self.id, n=self.reactant_id, z=self.component_id, c=self.coefficient)

class DBComponent(Base):
    '''
    Class representing the Component object. The component can belong to one of
    the 3 categories:
        * Zeolite component
        * Template
        * Zeolite Growth Modifier
    '''
    __tablename__ = 'components'

    id         = Column(Integer, primary_key=True)
    name       = Column(String)
    formula    = Column(String)
    molwt      = Column(Float)
    category   = Column(Integer, ForeignKey('categories.id'))
    short_name = Column(String)

    def __repr__(self):
        return "<DBComponent(id={i:>2d}, name='{n:s}', formula='{f:s}')>".format(
                i=self.id, n=self.name, f=self.formula)

class Chemical(Base):
    '''
    Class representing the Chemical object, (off the shelf reactants).
    '''
    __tablename__ = 'chemicals'

    id            = Column(Integer, primary_key=True)
    name          = Column(String)
    formula       = Column(String)
    molwt         = Column(Float)
    short_name    = Column(String)
    typ           = Column(Integer, ForeignKey('types.id'))
    concentration = Column(Float)
    cas           = Column(String)

    def __repr__(self):
        return "<Chemical(id={i:>2d}, name='{n:s}', formula='{f:s}')>".format(
                i=self.id, n=self.name, f=self.formula)

class Reactant(object):
    '''
    Class representing the Reactant object as it is used in the program.
    '''

    def __init__(self, id=None, name=None, formula=None, molwt=None,
                 short_name=None, typ=None, concentration=None, cas=None,
                 mass=0.0):

        self.id = id
        self.name = name
        self.formula = formula
        self.molwt = float(molwt)
        self.short_name = short_name
        self.typ = typ
        self.concentration = float(concentration)
        self.cas = cas
        self.mass = float(mass)

    def formula_to_tex(self):
        '''
        Convert the formula string to tex string.
        '''
        return re.sub(ur'(\d+)', ur'$_{\1}$', self.formula)

    def formula_to_html(self):
        '''
        Convert the formula string to html string.
        '''
        return re.sub(ur'(\d+)', ur'<sub>\1</sub>$', self.formula)

    def listctrl_label(self):
        '''
        Return the string to be displayed in the ListCtrl's.
        '''
        if self.short_name != "":
            res = self.short_name
        else:
            res = self.formula
        return res

    def label(self):
        '''
        Return a label to be used in printable tables (tex, html).
        '''
        if self.short_name != "":
            res = self.short_name + u" ({0:>4.1f}\%)".format(100*self.concentration)
        else:
            res = self.formula_to_tex() + u" ({0:>4.1f}\%)".format(100*self.concentration)
        return res

    def __repr__(self):
        return "<Reactant(id={i:>2d}, name='{n:s}', formula='{f:s}')>".format(
                i=self.id, n=self.name, f=self.formula)

class Component(object):
    '''
    Class representing the zeolite component object including the OSDA'a and ZGM's.
    '''
    def __init__(self, id=None, name=None, formula=None, molwt=None,
                 typ=None, short_name=None, moles=None, category=None):

        self.id = id
        self.name = name
        self.formula = formula
        self.molwt = float(molwt)
        self.short_name = short_name
        self.moles = float(moles)
        self.category = category

    @property
    def mass(self):
        return self.moles*self.molwt

    def formula_to_tex(self):
        '''
        Convert the formula string to tex string.
        '''
        return re.sub(ur'(\d+)', ur'$_{\1}$', self.formula)

    def formula_to_html(self):
        '''
        Convert the formula string to html string.
        '''
        return re.sub(ur'(\d+)', ur'<sub>\1</sub>$', self.formula)

    def listctrl_label(self):
        '''
        Return the string to be displayed in the ListCtrl's.
        '''
        if self.short_name != "":
            res = self.short_name
        else:
            res = self.formula
        return res

    def label(self):
        '''
        Return a label to be used in printable tables (tex, html).
        '''
        if self.short_name != "":
            res = self.short_name
        else:
            res = self.formula_to_tex()
        return res

    def __repr__(self):
        return "<Component(id={i:>2d}, name='{n:>15s}', formula='{f:>15s}', moles={m:8.2f})>".format(
                i=self.id, n=self.name, f=self.formula, m=self.moles)

class BatchCalculator(object):

    def __init__(self):

        # default database path
        dbpath = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                 pkg_resources.resource_filename("batchcalc", "data/zeolite.db"))

        self.new_dbsession(dbpath)

        self.lists = ["components", "reactants"]

        # create lists for different categories of
        for lst in self.lists:
            setattr(self, lst, list())

        self.A = list()
        self.B = list()
        self.X = list()

        self.scale_all = 100.0
        self.sample_scale = 1.0
        self.sample_size = 5.0
        self.selections = []

    def new_dbsession(self, dbpath):
        '''
        When new database ios chosed close the old session and establish a new
        one.
        '''

        if hasattr(self, "session"):
            self.session.close()
        engine = create_engine("sqlite:///{path:s}".format(path=dbpath))
        DBSession  = sessionmaker(bind=engine)
        self.session = DBSession()

    def reset(self):
        '''
        Clear the state of the calculation by reseting all the list and
        variables.
        '''

        self.components = []
        self.reactants = []

        self.A = []
        self.B = []
        self.X = []

        self.scale_all = 100.0
        self.sample_scale = 1.0
        self.sample_size = 5.0
        self.selections = []

    def get_component(self, category=None):
        '''
        Return all the components from a given category retrieved from the
        database, valid categories are:
            * template,
            * zeolite,
            * zgm
        '''

        categories = ["template", "zeolite", "zgm"]
        if category not in categories:
            raise ValueError("Wrong category in get_component:, got {0}, and allowed values are {1}".format(
                category, ", ".join(categories)))

        return self.session.query(DBComponent).\
                filter(DBComponent.category == Category.id).\
                filter(Category.name == category).all()

    def get_chemicals(self, showall=False):
        '''
        Return chemicals that are sources for the components present in the
        components list, of the list is empty return all the components.
        '''

        if showall:
            return self.session.query(Chemical,Types).filter(Chemical.typ == Types.id).all()
        else:
            res = set()
            for item in self.components:
                temp = self.session.query(Chemical, Types).join(Batch).\
                           filter(Chemical.typ == Types.id).\
                           filter(Batch.component_id == item.id).all()
                res.update(temp)
            out = list(res)
            return sorted(out, key=lambda x: x[0].id)

    def select_item(self, lst, attr, value):
        '''
        From a list of objects "lst" having a common attribute get the index of the
        object having the attribute "attr" set to "value".
        '''

        if lst not in self.lists:
            raise ValueError("wrong table in select_item")

        ag = operator.attrgetter(attr)
        for item in getattr(self, lst):
            if ag(item) == value:
                return item
        else:
            return None

    def update_components(self, category, selections):
        '''
        Based on the selections (list of 2-tuples) update the components list.
        '''

        if any(len(x) != 2 for x in selections):
            raise ValueError("selections should be tuples of length 2")

        for sitem in selections:
            comp, cat = self.session.query(DBComponent, Category).\
                    filter(DBComponent.category == Category.id).\
                    filter(DBComponent.id == sitem[0]).one()

            kwargs = {k : v for k, v in comp.__dict__.items() if not k.startswith('_')}
            kwargs["category"] = cat.name
            if int(sitem[0]) in [x.id for x in self.components]:
                # update the number of moles and concentration
                sobj = self.select_item("components", 'id', int(sitem[0]))
                sobj.moles = float(sitem[1])
            else:
                kwargs['moles'] = sitem[1]
                obj = Component(**kwargs)
                self.components.append(obj)

        # remove unselected items
        selid = [int(x[0]) for x in selections]
        cat_items = [x for x in self.components if x.id in selid and x.category == category]
        self.components = [x for x in self.components if x.category != category] + cat_items

    def update_reactants(self, selections):
        '''
        Based on the selections (list of 2-tuples) update the reactants list.
        '''

        if any(len(x) != 2 for x in selections):
            raise ValueError("selections should be tuples of length 2")

        for sitem in selections:
            reac, typ = self.session.query(Chemical, Types).\
                    filter(Chemical.typ==Types.id).\
                    filter(Chemical.id==int(sitem[0])).one()
            kwargs = {k : v for k, v in reac.__dict__.items() if not k.startswith('_')}
            kwargs["typ"] = typ.name
            if int(sitem[0]) in [x.id for x in self.reactants]:
                # update the number of moles
                sobj = self.select_item("reactants", "id", int(sitem[0]))
                sobj.concentration = float(sitem[1])
            else:
                kwargs['concentration'] = sitem[1]
                obj = Reactant(**kwargs)
                self.reactants.append(obj)

        # remove unselected items
        selid = [int(x[0]) for x in selections]
        self.reactants = [x for x in self.reactants if x.id in selid]

    def calculate(self):
        '''
        Solve the system of equations  B * X = C
        '''

        if len(self.components) == 0:
            raise ValueError("No Zeolite components selected")

        if len(self.reactants) == 0:
            raise ValueError(2, "No Reactants selected")

        if len(self.components) != len(self.reactants):
            raise ValueError("Number of zeolite components has to be equal to the " +
                      "number of reactants. " +
                      "You entered {0:<2d} zeolite components and {1:<2d} reactants.".format(\
                              len(self.components), len(self.reactants)))

        for comp in self.components:
            tempr = self.session.query(Chemical).join(Batch).filter(Batch.component_id == comp.id).all()
            if len(set([t.id for t in tempr]) & set([r.id for r in self.reactants])) == 0:
                raise ValueError("some compoennts need their sources: {0:s}".format(comp.name))

        self.A = self.get_A_matrix()
        self.B = self.get_B_matrix()

        try:
            self.X = solve(np.transpose(self.B), self.A)
            # assign calculated masses to the reactants
            for reac, x in zip(self.reactants, self.X):
                if reac.typ == "reactant":
                    reac.mass = x/reac.concentration
                else:
                    reac.mass = x
            return (0, "success")
        except Exception as e:
            raise e

    def get_A_matrix(self):
        '''
        Compose the [A] matrix with masses of zeolite components.
        '''

        return np.asarray([z.moles*z.molwt for z in self.components], dtype=float)

    def get_B_matrix(self):
        '''
        Construct and return the batch matrix [B].
        '''

        B = np.zeros((len(self.reactants), len(self.components)), dtype=float)

        for i, reactant in enumerate(self.reactants):
            comps = self.session.query(Batch,DBComponent).\
                    filter(Batch.reactant_id == reactant.id).\
                    filter(DBComponent.id==Batch.component_id).all()
            wfs = self.get_weight_fractions(i, comps)
            for j, comp in enumerate(self.components):
                for cid, wf in wfs:
                    if comp.id == cid:
                        B[i, j] = wf
        return B

    def get_weight_fractions(self, rindex, comps):
        '''
        Calculate the weight fractions corresponding to a specific reactant
        and coupled zolite componts.

        lower case "m": mass in grmas
        upper case "M": molecular weight [gram/mol]
        '''

        res = []

        if self.reactants[rindex].typ == "mixture":
            for batch, comp in comps:
                if comp.formula != "H2O":
                    res.append((comp.id, self.reactants[rindex].concentration))
                else:
                    res.append((comp.id, 1 - self.reactants[rindex].concentration))
            return res

        elif self.reactants[rindex].typ == "solution":
            if len(comps) > 2:
                raise ValueError("cannot handle cases of zeoindexes > 2")

            rct = self.reactants[rindex]

            h2o = self.session.query(Chemical).filter(Chemical.formula=="H2O").one()
            M_solv = h2o.molwt

            M_solu = rct.molwt

            if abs(rct.concentration - 1.0) > 0.0001:
                n_solu = M_solu*M_solv/(M_solv + (1.0-rct.concentration)*M_solu/rct.concentration)/M_solu
                n_solv = M_solu*M_solv/(M_solu + rct.concentration*M_solv/(1.0-rct.concentration))/M_solv
            else:
                n_solu = 1.0
                n_solv = 0.0

            masses = list()

            for batch, comp in comps:
                if comp.formula != "H2O":
                    masses.append(batch.coefficient*n_solu*comp.molwt)
                else:
                    masses.append((batch.coefficient*n_solu + n_solv)*comp.molwt)

            tot_mass = sum(masses)
            for batch, comp in comps:
                if comp.formula != "H2O":
                    res.append((comp.id, batch.coefficient*n_solu*comp.molwt/tot_mass))
                else:
                    res.append((comp.id, (batch.coefficient*n_solu + n_solv)*comp.molwt/tot_mass))
            return res

        elif self.reactants[rindex].typ == "reactant":
            if len(comps) > 1:
                tot_mass = sum([b.coefficient*c.molwt for b, c in comps])
                for batch, comp in comps:
                    res.append((comp.id, batch.coefficient*comp.molwt/tot_mass))
            else:
                res.append((comps[0][1].id, 1.0))
            return res

        else:
            raise ValueError("Unknown reactant typ: {}".format(self.reactants[rindex].typ))

    def rescale_all(self):
        '''
        Rescale all the resulting masses by a factor.
        '''

        res = [(s, s.mass/self.scale_all) for s in self.reactants]
        return res

    def rescale_to(self, sample_selections):
        '''
        Rescale all masses by a factor chosen in such a way that the sum of
        masses of a selected subset of chemicals is equal to the chose sample
        size.
        '''

        masses = [s.mass for s in self.reactants]
        self.sample_scale = sum([masses[i] for i in sample_selections])/float(self.sample_size)
        res = [(s, s.mass/self.sample_scale) for s in self.reactants]
        return res

    def print_A(self):
        '''
        Print the components vector in a readable form.
        '''

        width = max([len(c.listctrl_label()) for c in self.components] + [_minwidth])
        print "\n     {0:*^{w}s}\n".format("  "+ "Composition Vector [C]" +"  ", w=width+21)
        print " "*5 + "{l:^{wl}}  |{v:^15s}".format(
                    l="Formula", wl=width, v="Mass [g]")
        print " "*5 + "-"*(width+3+15)
        for reac in self.reactants:
            print " "*5+"{l:>{wl}}  |{v:>15.4f}".format(
                    l=reac.listctrl_label(), wl=width, v=reac.mass)

    def print_batch_matrix(self):
        '''
        Print the batch matrix in a readable form.
        '''

        lr = len(self.reactants)

        rowwidth = max([len(c.listctrl_label()) for c in self.components] + [_minwidth])
        colwidth = max([len(r.listctrl_label()) for r in self.reactants] + [_minwidth])

        print "\n{0}{1:*^{w}s}\n".format(" "*7, "  Batch Matrix [B]  ", w=(colwidth+1)*lr+rowwidth)
        print "{}".format(" "*(8+rowwidth))+"|".join(["{0:^{cw}s}".format(c.listctrl_label(), cw=colwidth) for c in self.components])
        print "{}".format(" "*(7+rowwidth))+"{}".format("-"*(colwidth+1)*lr)
        for reac, row in zip(self.reactants, self.B):
            print "     {0:>{w}s}  |".format(reac.listctrl_label(), w=rowwidth)+"|".join("{0:>{w}.4f}    ".format(x, w=colwidth-4) for x in row)

    def parse_formulas(self, string, delimiter=':'):
        '''
        Parse a string corresponding to the zeolite composition into a list of
        2-tuples.
        '''

        cre = re.compile(r'(?P<nmol>(-?\d+\.\d+|-?\d+))?\s*(?P<formula>[A-Za-z0-9\(\)]+)')
        result = []
        for comp in string.replace(" ", "").split(delimiter):
            m = cre.match(comp)
            if m:
                if m.group('nmol') is None:
                    nmol = 1.0
                else:
                    nmol = float(m.group('nmol'))
                result.append((m.group('formula'), nmol))
        return result