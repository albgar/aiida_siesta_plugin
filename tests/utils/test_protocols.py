#!/usr/bin/env runaiida
# -*- coding: utf-8 -*-
import os
from aiida_pseudo.groups.family.pseudo import PseudoPotentialFamily
from aiida_siesta.utils.protocols_system.protocols import ProtocolManager
#from aiida_siesta.groups.pseudos import PsmlFamily


def test_registries(aiida_profile):
    """
    Test that all the protocols are loaded, the one delivered in the package and
    the custom ones. It also loads a protocol with missing mandatory entries and it
    checks that an error is risen.
    """

    #Here I fake the pseudofamilies
    #PsmlFamily.objects.get_or_create("nc-sr-04_pbe_standard-psf")
    #PsmlFamily.objects.get_or_create("nc-sr-04_pbe_stringent-psf")
    #PsmlFamily.objects.get_or_create("nc-sr-04_pbe_standard_psml")
    PseudoPotentialFamily.objects.get_or_create("PseudoDojo/0.4/PBE/SR/standard/psml")

    basepath = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(basepath, 'fixtures/protocols/registries/custom_prot.yaml')

    os.environ["AIIDA_SIESTA_PROTOCOLS"] = filepath

    pmanager=ProtocolManager()
    assert 'standard_my' in pmanager.get_protocol_names()

    filepath = os.path.join(basepath, 'fixtures/protocols/registries/wrong_prot.yaml')
    os.environ["AIIDA_SIESTA_PROTOCOLS"] = filepath

    import pytest
    with pytest.raises(RuntimeError):
        pmanager=ProtocolManager()

    #A reset of the environment variable is needed at the end, otherwise it
    #messes up the other tests
    del os.environ['AIIDA_SIESTA_PROTOCOLS']


def test_methods(aiida_profile):
    """
    Test the 5 public methods of the class `ProtocolManager`
    """

    #Here I fake the pseudofamilies
    #PsmlFamily.objects.get_or_create("nc-sr-04_pbe_standard_psml")
    #PsmlFamily.objects.get_or_create("nc-sr-04_pbe_standard-psf")
    #PsmlFamily.objects.get_or_create("nc-sr-04_pbe_stringent-psf")
    PseudoPotentialFamily.objects.get_or_create("PseudoDojo/0.4/PBE/SR/standard/psml")

    pmanager=ProtocolManager()
        
    assert pmanager.is_valid_protocol("standard_psml")
    assert not pmanager.is_valid_protocol("yoyo")

    reflist = ["standard_psml"]
    plist = pmanager.get_protocol_names()
    assert plist == list(reflist)

    assert pmanager.get_default_protocol_name() == "standard_psml"

    import pytest
    with pytest.raises(ValueError):
        pmanager.get_protocol_info("yoyo")
    assert pmanager.get_protocol_info("standard_psml") == pmanager._protocols["standard_psml"]["description"]

    import pytest
    with pytest.raises(ValueError):
        pmanager.get_protocol("yoyo")
    assert pmanager.get_protocol("standard_psml") == pmanager._protocols["standard_psml"]
