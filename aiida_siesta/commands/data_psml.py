"""Implements the `verdi data psml` command."""

import io
import os
import click

from aiida.cmdline.commands.cmd_data import verdi_data
from aiida.cmdline.params import arguments, options
from aiida.cmdline.utils import decorators, echo


@verdi_data.group('psml')
def psml():
    """Manipulate PsmlData objects (PSML-format pseudopotentials)."""


@psml.command('uploadfamily')
@click.argument('folder', type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.argument('group_label', type=click.STRING)
@click.argument('group_description', type=click.STRING)
@click.option(
    '--stop-if-existing',
    is_flag=True,
    default=False,
    help='Interrupt pseudos import if a pseudo was already present in the AiiDA database'
)
@decorators.with_dbenv()
@decorators.deprecated_command(
    "This command has been deprecated and will be removed in v2.0. Please use `aiida-pseudo install` instead."
)
def psml_uploadfamily(folder, group_label, group_description, stop_if_existing):
    """
    Create a new PSML family from a folder of PSML files.

    Returns the numbers of files found and the number of nodes uploaded.

    Call without parameters to get some help.
    """
    from aiida_siesta.data.psml import upload_psml_family
    files_found, files_uploaded = upload_psml_family(folder, group_label, group_description, stop_if_existing)
    echo.echo_success('PSML files found: {}. New files uploaded: {}'.format(files_found, files_uploaded))


@psml.command('listfamilies')
@click.option(
    '-d',
    '--with-description',
    'with_description',
    is_flag=True,
    default=False,
    help='Show also the description for the PSML family'
)
@options.WITH_ELEMENTS()
@decorators.with_dbenv()
@decorators.deprecated_command(
    "This command is deprecated and will be removed in aiida_siesta v2.0. Its substitute command is `aiida-pseudo "
    "list`. Since the pseudo management is now based on a new system, the families listed here will not appear "
    "running the new command. It is suggested to export the families into a folder (`verdi data psml exportfamily "
    "folder_name family_label`), delete the group corresponding to the family (`verdi group delete family_label`), "
    "and install the family again (`aiida-pseudo install family folder_name family_label -P pseudo.psml`)."
)
def psml_listfamilies(elements, with_description):
    """
    List all PSML families that exist in the database.
    """
    from aiida import orm
    from aiida.plugins import DataFactory
    from aiida_siesta.groups.pseudos import PsmlFamily

    PsmlData = DataFactory('siesta.psml')  # pylint: disable=invalid-name
    query = orm.QueryBuilder()
    query.append(PsmlData, tag='psmldata')
    if elements is not None:
        query.add_filter(PsmlData, {'attributes.element': {'in': elements}})
    query.append(PsmlFamily, with_node='psmldata', tag='group', project=['label', 'description'])

    query.distinct()
    if query.count() > 0:
        for res in query.dict():
            group_label = res.get('group').get('label')
            group_desc = res.get('group').get('description')
            query = orm.QueryBuilder()
            query.append(orm.Group, tag='thisgroup', filters={'label': {'like': group_label}})
            query.append(PsmlData, project=['id'], with_group='thisgroup')

            if with_description:
                description_string = ': {}'.format(group_desc)
            else:
                description_string = ''

            echo.echo_success('* {} [{} pseudos]{}'.format(group_label, query.count(), description_string))

    else:
        echo.echo_warning('No valid PSML pseudopotential family found.')


@psml.command('exportfamily')
@click.argument('folder', type=click.Path(exists=True, file_okay=False, resolve_path=True))
@arguments.GROUP()
@decorators.with_dbenv()
@decorators.deprecated_command("This command has been deprecated and will be removed in v2.0.")
def psml_exportfamily(folder, group):
    """
    Export a pseudopotential family into a folder.
    Call without parameters to get some help.
    """
    if group.is_empty:
        echo.echo_critical('Group<{}> contains no pseudos'.format(group.label))

    for node in group.nodes:
        dest_path = os.path.join(folder, node.filename)
        if not os.path.isfile(dest_path):
            with io.open(dest_path, 'w', encoding='utf8') as handle:
                handle.write(node.get_content())
        else:
            echo.echo_warning('File {} is already present in the destination folder'.format(node.filename))


@psml.command('import')
@click.argument('filename', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@decorators.with_dbenv()
@decorators.deprecated_command("This command has been deprecated and will be removed in v2.0.")
def psml_import(filename):
    """
    Import a PSML pseudopotential from a file.
    """
    from aiida_siesta.data.psml import PsmlData

    node, _ = PsmlData.get_or_create(filename)
    echo.echo_success('Imported: {}'.format(node))
