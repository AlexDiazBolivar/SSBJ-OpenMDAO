"""
SSBJ test case - http://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/19980234657.pdf
Python implementation and OpenMDAO integration developed by
Sylvain Dubreuil and Remi Lafage of ONERA, the French Aerospace Lab.
"""
import numpy as np
from openmdao.api import Group, ExecComp, IndepVarComp

from disciplines.aerodynamics import Aerodynamics
from disciplines.performance import Performance
from disciplines.propulsion import Propulsion
from disciplines.structure import Structure
# pylint: disable=C0103

class SSBJ_IDF_MDA(Group):
    """
    Analysis for IDF formulation where couplings are managed as additional constraints
    on input/output variables of related disciplines.
    """
    def __init__(self, scalers):
        super(SSBJ_IDF_MDA, self).__init__()
        self.scalers = scalers

    def setup(self):        
        #Design variables
        self.add_subsystem('z_ini', IndepVarComp('z', np.array([1.2,  1.,  1.,  1.,  1.,  1.])), 
                 promotes=['*'])
        self.add_subsystem('x_aer_ini', IndepVarComp('x_aer', 1.), promotes=['*'])
        self.add_subsystem('x_str_ini', IndepVarComp('x_str', np.array([1. ,  1.])), promotes=['*'])
        self.add_subsystem('x_pro_ini', IndepVarComp('x_pro', 1.), promotes=['*'])

        self.add_subsystem('L_ini', IndepVarComp('L', 0.888), promotes=['*'])
        self.add_subsystem('WE_ini', IndepVarComp('WE', 1.490), promotes=['*'])
        self.add_subsystem('WT_ini', IndepVarComp('WT', 0.888), promotes=['*'])
        self.add_subsystem('Theta_ini', IndepVarComp('Theta', 0.997), promotes=['*'])
        self.add_subsystem('ESF_ini', IndepVarComp('ESF', 1.463), promotes=['*'])
        self.add_subsystem('D_ini', IndepVarComp('D', 0.457), promotes=['*'])

        #Disciplines
        self.add_subsystem('Struc', Structure(self.scalers))
        self.add_subsystem('Aero', Aerodynamics(self.scalers))
        self.add_subsystem('Propu', Propulsion(self.scalers))
        self.add_subsystem('Perfo', Performance(self.scalers))

        #Shared variables z
        self.connect('z', 'Struc.z')
        self.connect('z', 'Aero.z')
        self.connect('z', 'Propu.z')
        self.connect('z', 'Perfo.z')

        # Local variables
        self.connect('x_str', 'Struc.x_str')
        self.connect('x_aer', 'Aero.x_aer')
        self.connect('x_pro', 'Propu.x_pro')

        # Coupling variables
        self.connect('L', 'Struc.L')
        self.connect('WE', 'Struc.WE')
        self.connect('WT', 'Aero.WT')
        self.connect('Theta', 'Aero.Theta')
        self.connect('ESF', 'Aero.ESF')
        self.connect('D','Propu.D')

        # Objective function
        self.add_subsystem('Obj', ExecComp('obj=-R'), promotes=['obj'])

        # Connections
        self.connect('Perfo.R','Obj.R')
        self.connect('Propu.SFC','Perfo.SFC')
        self.connect('Aero.fin','Perfo.fin')
        self.connect('Struc.WT','Perfo.WT')
        self.connect('Struc.WF','Perfo.WF')

        #Coupling constraints
        self.add_subsystem('con_Str_Aer_WT', ExecComp('con_str_aer_wt = (WTi-WT)**2',WTi=1.0),
                 promotes=['con_str_aer_wt'])
        self.connect('Struc.WT','con_Str_Aer_WT.WT')
        self.connect('WT','con_Str_Aer_WT.WTi')

        self.add_subsystem('con_Str_Aer_Theta', ExecComp('con_str_aer_theta = (Thetai-Theta)**2'),
                 promotes=['con_str_aer_theta'])
        self.connect('Struc.Theta', 'con_Str_Aer_Theta.Theta')
        self.connect('Theta', 'con_Str_Aer_Theta.Thetai')

        self.add_subsystem('con_Aer_Str_L', ExecComp('con_aer_str_l = (Li-L)**2'),
                 promotes=['con_aer_str_l'])
        self.connect('Aero.L','con_Aer_Str_L.L')
        self.connect('L','con_Aer_Str_L.Li')

        self.add_subsystem('con_Aer_Pro_D', ExecComp('con_aer_pro_d = (Di-D)**2'),
                 promotes=['con_aer_pro_d'])
        self.connect('Aero.D','con_Aer_Pro_D.D')
        self.connect('D','con_Aer_Pro_D.Di')

        self.add_subsystem('con_Pro_Aer_ESF', ExecComp('con_pro_aer_esf = (ESFi-ESF)**2'),
                 promotes=['con_pro_aer_esf'])
        self.connect('Propu.ESF','con_Pro_Aer_ESF.ESF')
        self.connect('ESF','con_Pro_Aer_ESF.ESFi')

        self.add_subsystem('con_Pro_Str_WE',ExecComp('con_pro_str_we = (WEi-WE)**2'),
                 promotes=['con_pro_str_we'])
        self.connect('Propu.WE','con_Pro_Str_WE.WE')
        self.connect('WE','con_Pro_Str_WE.WEi')

        #Local constraints
        self.add_subsystem('con_Theta_sup', 
                 ExecComp('con_Theta_up = Theta*'+str(self.scalers['Theta'])+'-1.04'),
                 promotes=['con_Theta_up'])
        self.connect('Theta','con_Theta_sup.Theta')

        self.add_subsystem('con_Theta_inf',
                 ExecComp('con_Theta_low = 0.96-Theta*'+str(self.scalers['Theta'])),
                 promotes=['con_Theta_low'])

        self.connect('Theta','con_Theta_inf.Theta')
        for i in range(5):
            self.add_subsystem('con_Sigma'+str(i+1),
                     ExecComp('con_sigma'+str(i+1)+'=sigma['+str(i)+']*'+\
                              str(self.scalers['sigma'][i])+'-1.9',
                              sigma=np.zeros(5)),
                     promotes=['con_sigma'+str(i+1)])
            self.connect('Struc.sigma','con_Sigma'+str(i+1)+'.sigma')

        self.add_subsystem('con_Dpdx',ExecComp('con_dpdx=dpdx*'+str(self.scalers['dpdx'])+'-1.04'),
                 promotes=['con_dpdx'])
        self.connect('Aero.dpdx','con_Dpdx.dpdx')

        self.add_subsystem('con_ESF', ExecComp('con_esf=ESF*'+str(self.scalers['ESF'])+'-1.5'),
                 promotes=['con_esf'])
        self.connect('ESF','con_ESF.ESF')

        self.add_subsystem('con_Temp', ExecComp('con_temp=Temp*'+str(self.scalers['Temp'])+'-1.0'),
                 promotes=['con_temp'])
        self.connect('Propu.Temp', 'con_Temp.Temp')
        
        self.add_subsystem('con_DT', ExecComp('con_dt=DT'), promotes=['con_dt'])
        self.connect('Propu.DT', 'con_DT.DT')

