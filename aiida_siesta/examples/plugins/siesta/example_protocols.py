#!/usr/bin/env runaiida
"""
File showcasing the submission of a SiestaCalculation using the protocol system.
"""
import sys
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida.engine import submit
from aiida.orm import Dict, StructureData


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
    codename = 'SiestaHere@localhost'

#Three are the mandatory inputs: structure, a dictionary with the comp resources
#(calc_engines) and the protocol name

alat = 5.430  # angstrom
cell = [[0.5 * alat, 0.5 * alat, 0.,],
        [0., 0.5 * alat, 0.5 * alat,],
        [0.5 * alat, 0., 0.5 * alat,],
        ]
structure = StructureData(cell=cell)
structure.append_atom(position=(0.000 * alat, 0.000 * alat, 0.000 * alat),
                      symbols=['Si'])
structure.append_atom(position=(0.250 * alat, 0.250 * alat, 0.250 * alat),
                      symbols=['Si'])

calc_engines = {
     'siesta': {
         'code': codename, 
         'options': {
             'resources': {'num_machines': 1, "num_mpiprocs_per_machine": 1}, 
             "max_wallclock_seconds": 3600, #'queue_name': 'DevQ', 'withmpi': True, 'account': "tcphy113c"
         }}}

protocol="standard_psml"

#Optionally, the bands calculation can be requested adding in inputs the `path_generator` parameter.
#Two options availables, the "legacy" option (no change of structure but wrong for some crystalin
#systems) and "seekpath"
path_generator = "seekpath"

#Optionally, the relaxation can be requested adding in inputs the `relaxation_type` parameter.
#At the moment the options "atoms_only", "variable_cell", "constant_volume" are available
relaxation_type = "atoms_only"

#Optionally, the spin polarization can be requested adding in inputs the `spin` parameter.
#The options "polarized", "non-collinear", "spin-orbit" are available
spin = "polarized"


inp_gen = SiestaCalculation.inputs_generator()
builder = inp_gen.get_filled_builder(structure, calc_engines, protocol)
#builder = inp_gen.get_builder(structure, calc_engines, protocol, path_generator, relaxation_type, spin)

#The inputs generator (inp_gen) has also some
#methods to guide the construction, like:
#print(inp_gen.get_relaxation_types())
#print(inp_gen.get_protocol_names())
#print(inp_gen.how_to_pass_computation_options())

# As we get the builder and not stored nodes, before submission any user has complete
# freedom to change something before submission.
# If no change is performed, just submitting the builder should still work and produce sensible results.
new_params = builder.parameters.get_dict()
new_params['max_scf_iterations'] = 200
builder.parameters = Dict(dict=new_params)

# Here we just submit the builder
if submit_test:
    builder.metadata["dry_run"] = True 
    builder.metadata["store_provenance"] = False
    process = submit(builder)
    print("Submited test for calculation (uuid='{}')".format(process.uuid))
    print("Check the folder submit_test for the result of the test")

else:
    process = submit(builder)
    print("Submitted calculation; ID={}".format(process.pk))
    print("For information about this calculation type: verdi process show {}".format(process.pk))
    print("For a list of running processes type: verdi process list")

