#!/usr/bin/env runaiida
import os.path as op
import sys

#In this example we will calculate the band structure of Si.
#Thanks to SeeK-path we can automatically generate the
#high symmetry points path where to calculate the bands.
#Alternatively, a manual list of k-points can be set.

################################################################

import io
from aiida.engine import submit
from aiida.orm import load_code
from aiida.orm import (Dict, StructureData, KpointsData)
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida_pseudo.data.pseudo.psf import PsfData
from aiida.tools import get_explicit_kpoints_path


try:
    dontsend = sys.argv[1]
    if dontsend == "--dont-send":
        submit_test = True
    elif dontsend == "--send":
        submit_test = False
    else:
        raise IndexError
except IndexError:
    print(("The first parameter can only be either "
           "--send or --dont-send"),
          file=sys.stderr)
    sys.exit(1)

try:
    codename = sys.argv[2]
except IndexError:
    codename = 'Siesta4.0.1@kelvin'

#The code
code = load_code(codename)

##-------------------Structure-----------------------------------
##Manually set the structure, all the quantities must be in Ang.
##Then, we pass through SeeK-path, to get the standardized cell,
##necessary for the automatic choice of the bands path.
alat = 5.430  # angstrom
cell = [
    [
        0.5 * alat,
        0.5 * alat,
        0.,
    ],
    [
        0.,
        0.5 * alat,
        0.5 * alat,
    ],
    [
        0.5 * alat,
        0.,
        0.5 * alat,
    ],
]

s = StructureData(cell=cell)
s.append_atom(position=(0.000 * alat, 0.000 * alat, 0.000 * alat),
              symbols=['Si'])
s.append_atom(position=(0.250 * alat, 0.250 * alat, 0.250 * alat),
              symbols=['Si'])

elements = list(s.get_symbols_set())

seekpath_parameters = Dict(dict={
    'reference_distance': 0.02,
    'symprec': 0.0001
})
result = get_explicit_kpoints_path(s, **seekpath_parameters.get_dict())
structure = result['primitive_structure']

#The parameters
parameters = Dict(
    dict={
        'xc-functional': 'LDA',
        'xc-authors': 'CA',
        'max-scfiterations': 50,
        'dm-numberpulay': 4,
        'dm-mixingweight': 0.3,
        'dm-tolerance': 1.e-3,
        'Solution-method': 'diagon',
        'electronic-temperature': '25 meV',
        'write-forces': True,
    })

#The basis
basis = Dict(dict={
'pao-energy-shift': '300 meV',
'%block pao-basis-sizes': """
Si DZP
%endblock pao-basis-sizes""",
    })

#The kpoints mesh
kpoints = KpointsData()
kpoints.set_kpoints_mesh([4, 4, 4])

##-------------------K-points for bands --------------------
bandskpoints = KpointsData()
##Uncomment your favourite, three options:
##1)
##.....Making use of SeeK-path for the automatic path......
##The choice of the distance between kpoints is in the call seekpath_parameters
##All high symmetry points included, labels already included
##This calls BandLine in siesta
bandskpoints = result['explicit_kpoints']
##2)
##.................Only discrete points.............
##This calls BandsPoint
#kpp = [(0.500,  0.250, 0.750), (0.500,  0.500, 0.500), (0., 0., 0.)]
#bandskpoints.set_kpoints(kpp)
##3)
##...The option to define a path touching specific kpoints...
##It make use of a legacy function.
#from aiida.tools.data.array.kpoints.legacy import get_explicit_kpoints_path as legacy_path
#kpp = [('W',  (0.500,  0.250, 0.750), 'L', (0.500,  0.500, 0.500), 40),
#        ('L', (0.500,  0.500, 0.500), 'G', (0., 0., 0.), 40)]
#tmp=legacy_path(kpp)
#bandskpoints.set_kpoints(tmp[3])
#bandskpoints.labels=tmp[4]

#The pseudopotentials
pseudos_dict = {}
raw_pseudos = [("Si.psf", ['Si'])]
for fname, kinds in raw_pseudos:
    absname = op.realpath(op.join(op.dirname(__file__), "../../fixtures/sample_psf", fname))
    with io.open(absname, 'rb') as handle:
        pseudo = PsfData.get_or_create(handle)
    if not pseudo.is_stored:
        print("\nCreated the pseudo for {}".format(kinds))
    else:
        print("\nUsing the pseudo for {} from DB: {}".format(kinds, pseudo.pk))
    for j in kinds:
        pseudos_dict[j]=pseudo

#Resources
options = {
    "max_wallclock_seconds": 600,
#    "withmpi" : True,
    "resources": {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 1,
    }
}

inputs = {
    'structure': structure,
    'parameters': parameters,
    'code': code,
    'basis': basis,
    'kpoints': kpoints,
    'bandskpoints': bandskpoints,
    'pseudos': pseudos_dict,
    'metadata': {
        "label": "TestOnSiliconBands",
        'options': options,
    }
}

if submit_test:
    inputs["metadata"]["dry_run"] = True
    inputs["metadata"]["store_provenance"] = False
    process = submit(SiestaCalculation, **inputs)
    #    subfolder, script_filename = calc.submit_test()
    print("Submited test for calculation (uuid='{}')".format(process.uuid))
    print("Check the folder submit_test for the result of the test")
# I could't find a way to access the actual folder (subfolder of submit_test)
# from the calculation node. So I can't print the exact location

else:
    process = submit(SiestaCalculation, **inputs)
    print("Submitted calculation; ID={}".format(process.pk))
    print("For information about this calculation type: verdi process show {}".
          format(process.pk))
    print("For a list of running processes type: verdi process list")
