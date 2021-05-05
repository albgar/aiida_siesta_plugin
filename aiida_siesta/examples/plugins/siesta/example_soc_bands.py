#!/usr/bin/env runaiida

import os.path as op
import sys
from aiida.tools import get_explicit_kpoints_path
import io

#In this example we will calculate the band structure of Ge with SOC.
#Thanks to SeeK-path we can automatically generate the
#high symmetry points path where to calculate the bands.
#Alternatively, a manual list of k-points can be set.

################################################################

from aiida.engine import submit
from aiida.orm import load_code
from aiida.orm import (Dict, StructureData, KpointsData)
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida.plugins import DataFactory

PsfData = DataFactory('pseudo.psf')

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
    codename = 'Siesta4.1-b3@kelvin'

##-------------------Structure-----------------------------------
##Manually set the structure, all the quantities must be in Ang.
##Then, we pass through SeeK-path, to get the standardized cell,
##necessary for the automatic choice of the bands path.

alat = 5.65  # angstrom
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
              symbols=['Ge'])
s.append_atom(position=(0.250 * alat, 0.250 * alat, 0.250 * alat),
              symbols=['Ge'])

elements = list(s.get_symbols_set())

seekpath_parameters = Dict(dict={
    'reference_distance': 0.02,
    'symprec': 0.0001
})
result = get_explicit_kpoints_path(s, **seekpath_parameters.get_dict())
structure = result['primitive_structure']

code = load_code(codename)

parameters = Dict(
    dict={
        'xc-functional': 'GGA',
        'xc-authors': 'PBE',
        'max-scfiterations': 50,
        'dm-numberpulay': 4,
        'Spin': "SO",
        'dm-mixingweight': 0.3,
        'dm-tolerance': 1.e-3,
        'electronic-temperature': '25 meV'
    })

basis = Dict(
    dict={
        'pao-energy-shift': '300 meV',
        '%block pao-basis-sizes': """
Ge DZP
%endblock pao-basis-sizes""",
    })

kpoints = KpointsData()
kpoints.set_kpoints_mesh([4, 4, 4])

##-------------------K-points for bands --------------------
bandskpoints = KpointsData()

##.....Making use of SeeK-path for the automatic path......
##The choice of the distance between kpoints is in the call seekpath_parameters
##All high symmetry points included, labels already included
##This calls BandLine in siesta
bandskpoints = result['explicit_kpoints']


# Pseudopotentials
pseudos_dict = {}
raw_pseudos = [("Ge.psf", ['Ge'])]
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


options = {
#    "queue_name": "DevQ",
#    'account' : "tcphy107c",
    "max_wallclock_seconds": 1200,
    "withmpi" : True,
    "resources": {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 2,
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
        "label": "Ge band-structure with SOC",
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

else:
    process = submit(SiestaCalculation, **inputs)
    print("Submitted calculation; ID={}".format(process.pk))
    print("For information about this calculation type: verdi process show {}".
          format(process.pk))
    print("For a list of running processes type: verdi process list")
