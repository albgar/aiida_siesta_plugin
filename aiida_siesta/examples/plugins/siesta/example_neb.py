#!/usr/bin/env runaiida

#Not required by AiiDA
import os.path as op
import sys
import io

#AiiDA classes and functions
from aiida.engine import submit
from aiida.orm import load_code
from aiida.orm import (Dict, List, StructureData, KpointsData)
from aiida.orm import SinglefileData, FolderData
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida_pseudo.data.pseudo.psf import PsfData

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

cell = [[15.0, 00.0 , 00.0,],
        [00.0, 15.0 , 00.0,],
        [00.0, 00.0 , 15.0,],
        ]
s = StructureData(cell=cell)
s.append_atom(position=( 0.000,  0.000,  0.000 ),symbols=['O']) #1
s.append_atom(position=( 0.757,  0.586,  0.000 ),symbols=['H']) #2
s.append_atom(position=(-0.757,  0.586,  0.000 ),symbols=['H']) #3 
s.append_atom(position=( 0.000,  3.500,  0.000 ),symbols=['O']) #4
s.append_atom(position=( 0.757,  2.914,  0.000 ),symbols=['H']) #5
s.append_atom(position=(-0.757,  2.914,  0.000 ),symbols=['H']) #6

#--------------------  Lua block
# lua script
absname = op.abspath(op.join(op.dirname(__file__), "../../fixtures/lua_scripts/neb.lua"))
lua_script = SinglefileData(absname)

# Lua input files
xyz_folder = op.abspath(op.join(op.dirname(__file__), "../../fixtures/neb_data"))
lua_input_files = FolderData(tree=xyz_folder)

# Lua parameters
lua_parameters = {
    'number_of_internal_images_in_path': 5,
    'neb_spring_constant': 0.45,
    'neb_image_file_prefix': "image-"
    }

# Lua retrieve list: output image files and results
lua_retrieve_list = [ '*.xyz', 'NEB.results' ]
#-------------------- 


#The parameters
parameters = Dict(dict={
   "mesh-cutoff": "50 Ry",
   "dm-tolerance": "0.0001",
   "DM-NumberPulay ":  "3",
   "DM-History-Depth":  "0",
   "SCF-Mixer-weight":  "0.02",
   "SCF-Mix":   "density",
   "SCF-Mixer-kick":  "35",
   "MD-VariableCell":  "F",
   "MD-MaxCGDispl":  "0.3 Bohr",
   "MD-MaxForceTol":  " 0.04000 eV/Ang",
    "%block Geometry-Constraints":
    """
    atom [1 -- 4]
    %endblock Geometry-Constraints"""
    })

basis = Dict(dict={
  "%block PAO-Basis":
    """
 O                     2                    # Species label, number of l-shells
 n=2   0   2                         # n, l, Nzeta
   3.305      2.510
   1.000      1.000
 n=2   1   2 P   1                   # n, l, Nzeta, Polarization, NzetaPol
   3.937      2.542
   1.000      1.000
H                     1                    # Species label, number of l-shells
 n=1   0   2 P   1                   # n, l, Nzeta, Polarization, NzetaPol
   4.828      3.855
   1.000      1.000

    %endblock PAO-Basis""",
})


#The kpoints
#kpoints = KpointsData()
#kpoints.set_kpoints_mesh([1, 1, 1])

#The pseudopotentials
pseudos_dict = {}
raw_pseudos = [ ("H.psf", ['H']),("O.psf", ['O'])]
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




#####!!!!!!!!!!!!! THIS VARIABLE MUST BE CHANGED !!!!!!!!!!!###########
#The lua elements from flos library. The path must be an explicit path!
lua_elements_path = "/home/ebosoni/flos/?.lua;/home/ebosoni/flos/?/init.lua;/home/ebosoni/flos/examples/neb_simple.lua;"


#Resources
options = {
    "max_wallclock_seconds": 3600,
    'withmpi': True,
    "resources": {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 2,
    },
    "environment_variables":{"LUA_PATH":lua_elements_path},
}


#The submission
#All the inputs of a Siesta calculations are listed in a dictionary
inputs = {
    'lua': { 'script': lua_script,
             'input_files': lua_input_files,
             'parameters': Dict(dict=lua_parameters),
             'retrieve_list': List(list=lua_retrieve_list)
             },

    'structure': s,
    'parameters': parameters,
    'code': code,
    'basis': basis,
    'pseudos': pseudos_dict,
    'metadata': {
        "label": "Some NEB test with H and O",
        'options': options,
    }
}

if submit_test:
    inputs["metadata"]["dry_run"] = True
    inputs["metadata"]["store_provenance"] = False
    process = submit(SiestaCalculation, **inputs)
    print("Submited test for calculation (uuid='{}')".format(process.uuid))
    print("Check the folder submit_test for the result of the test")

else:
    process = submit(SiestaCalculation, **inputs)
    print("Submitted calculation; ID={}".format(process.pk))
    print("For information about this calculation type: verdi process show {}".
          format(process.pk))
    print("For a list of running processes type: verdi process list")

##An alternative is be to use the builder
#build=SiestaCalculation.get_builder()
#build.code=code
#build.structure=structure
#build.pseudos=pseudos_dict
#...
#build.metadata.options.resources = {'num_machines': 1 "num_mpiprocs_per_machine": 1}
#process = submit(builder)


