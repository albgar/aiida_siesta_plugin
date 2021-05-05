#!/usr/bin/env runaiida
# -*- coding: utf-8 -*-
from aiida.plugins import WorkflowFactory, CalculationFactory


def test_siestacalc_inpgen(aiida_profile, fixture_code, generate_structure, generate_psml_fam):
    """Test the validation of subclasses of `InputsGenerator`."""

    generate_psml_fam("PseudoDojo/0.4/PBE/SR/standard/psml","Si") #This will stay for the entire session!

    from aiida_siesta.utils.protocols_system.input_generators import SiestaCalculationInputGenerator

    inp_gen = SiestaCalculationInputGenerator(CalculationFactory("siesta.siesta"))
    structure = generate_structure()
    protocol = inp_gen.get_default_protocol_name()
    code = fixture_code("siesta.siesta")
    code.store()
    calc_engines = {"siesta": {'code': code.uuid, 'options': {"resources": {"num_mpiprocs_per_machine": 1}, "max_wallclock_seconds": 360}}}

    build = inp_gen.get_filled_builder(structure, calc_engines, protocol, spin="polarized")

    assert "parameters" in build


def test_baseworkchain_inpgen(aiida_profile, fixture_code, generate_structure):
    """Test the validation of subclasses of `InputsGenerator`."""

    from aiida_siesta.utils.protocols_system.input_generators import BaseWorkChainInputGenerator

    inp_gen = BaseWorkChainInputGenerator(WorkflowFactory("siesta.base"))
    structure = generate_structure()
    protocol = inp_gen.get_default_protocol_name()
    code = fixture_code("siesta.siesta")
    code.store()
    calc_engines = {"siesta": {'code': code.uuid, 'options': {"resources": {"num_mpiprocs_per_machine": 1}, "max_wallclock_seconds": 360}}} 

    build = inp_gen.get_filled_builder(structure, calc_engines, protocol, spin="polarized")

    assert "parameters" in build


def test_eosworkchain_inpgen(aiida_profile, fixture_code, generate_structure):
    """Test the validation of subclasses of `InputsGenerator`."""

    from aiida_siesta.utils.protocols_system.input_generators import EosWorkChainInputGenerator

    inp_gen = EosWorkChainInputGenerator(WorkflowFactory("siesta.eos"))
    structure = generate_structure()
    protocol = inp_gen.get_default_protocol_name()
    code = fixture_code("siesta.siesta")
    code.store()
    calc_engines = {"siesta": {'code': code.uuid, 'options': {"resources": {"num_mpiprocs_per_machine": 1}, "max_wallclock_seconds": 360}}}

    build = inp_gen.get_filled_builder(structure, calc_engines, protocol, relaxation_type="atoms_only")

    assert "parameters" in build

def test_stmworkchain_inpgen(aiida_profile, fixture_code, generate_structure):
    """Test the validation of subclasses of `InputsGenerator`."""

    from aiida_siesta.utils.protocols_system.input_generators import StmWorkChainInputGenerator

    inp_gen = StmWorkChainInputGenerator(WorkflowFactory("siesta.stm"))
    structure = generate_structure()
    protocol = inp_gen.get_default_protocol_name()
    code = fixture_code("siesta.siesta")
    code.store()
    code2 = fixture_code("siesta.stm")
    code2.store()
    calc_engines = {"siesta": {'code': code.uuid, 'options': {"resources": {"num_mpiprocs_per_machine": 1}, "max_wallclock_seconds": 360}},
                    "stm": {'code': code2.uuid, 'options': {"resources": {"num_mpiprocs_per_machine": 1}, "max_wallclock_seconds": 360}}
            }

    build = inp_gen.get_filled_builder(structure, calc_engines, protocol, stm_mode="constant-height", stm_value=2)

    assert "parameters" in build
