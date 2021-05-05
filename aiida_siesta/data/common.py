import warnings
from aiida.orm import Group
from aiida_siesta.data.psf import PsfData
from aiida_siesta.data.psml import PsmlData
from aiida_siesta.utils.warn import AiidaSiestaDeprecationWarning

message = (  #pylint: disable=invalid-name
    'This module has been deprecated and will be removed in `v2.0.0`. Function `get_pseudos_from_structure` ' +
    'is no longer needed. Its functionality is substitued by `fam.get_pseudos(structure=structure)` ' +
    'where `fam` is an instance of the families classes in `aiida_pseudo.groups.family`.'
)

warnings.warn(message, AiidaSiestaDeprecationWarning)


def get_pseudos_from_structure(structure, family_name):
    """Given a family name (a Siesta pseudo group in the DB, possibly with
    mixed psf and psml pseudopotentials) and an AiiDA structure
    object, return a dictionary associating each 'kind' name in the
    structure with its object (PsfData or PsmlData).

    :raise MultipleObjectsError: if more than one pseudo for the same
       element is found in the group.

    :raise NotExistent: if no pseudo for an element in the group is
       found in the group.

    """
    from aiida.common.exceptions import NotExistent, MultipleObjectsError

    family_pseudos = {}
    family = Group.get(label=family_name)
    for node in family.nodes:
        if isinstance(node, (PsfData, PsmlData)):
            if node.element in family_pseudos:
                raise MultipleObjectsError(
                    "More than one pseudo for element {} found in "
                    "family {}".format(node.element, family_name)
                )
            family_pseudos[node.element] = node

    pseudo_list = {}
    for kind in structure.kinds:
        symbol = kind.symbol
        try:
            pseudo_list[kind.name] = family_pseudos[symbol]
        except KeyError:
            raise NotExistent("No pseudo for element {} found in family {}".format(symbol, family_name))

    return pseudo_list
