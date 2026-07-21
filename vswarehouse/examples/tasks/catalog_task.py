import os
import requests
import json
import argparse
import subprocess
import traceback
import sys
import urllib3

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CatalogExistsError(Exception):
    """Exception raised when attempting to create a catalog that already exists."""
    pass

def get_request_setup() -> tuple:
    """
    Get common setup for making API requests.

    Returns:
        tuple: (server_url, workspace_id, session_key, headers)
    """
    # Get environment variables
    server_url = os.environ.get('GH_SERVER_URL')
    workspace_id = os.environ.get('GH_WORKSPACE_ID')
    session_key = os.environ.get('GH_SESSION_KEY')

    if not all([server_url, workspace_id, session_key]):
        raise ValueError("Missing required environment variables: GH_SERVER_URL, GH_WORKSPACE_ID, or GH_SESSION_KEY")

    # Prepare headers
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'Cookie': f'GH_SessKey={session_key}'
    }

    return server_url, workspace_id, session_key, headers

def reload_workspace_catalogs() -> None:
    """
    Ask the workspace API server to re-scan its Catalogs directory.

    gautil writes the GeneLists / GenePreferences catalogs straight to disk (out-of-band), so the
    already-running API server -- which builds its catalog list once and only refreshes it when a
    catalog is created through its own REST API -- will not surface them until it re-scans. Trigger
    that re-scan so the new gene catalogs are immediately visible to clients (catalog pickers,
    named-source lookups). The REST-created catalogs above register themselves and need no reload.
    """
    server_url, workspace_id, _, headers = get_request_setup()
    url = f"{server_url}/w/{workspace_id}/api/catalogs/reload"
    response = requests.post(url, headers=headers, data="{}", verify=False)
    if response.status_code >= 400:
        raise requests.exceptions.HTTPError(f"HTTP {response.status_code}: {response.text}")

def create_catalog(template_id: str, id: str, name: str, description: str, group: str, approval_count: int = 0) -> dict:
    """
    Create a new catalog using a system template.

    Args:
        template_id (str): The ID of the template to use
        id (str): The ID of the catalog to create
        name (str): Name of the catalog
        description (str): Description of the catalog
        group (str): Group for the catalog
        approval_count (int, optional): Number of approvals required. Defaults to 0.

    Returns:
        dict: The response from the API
    """
    # Get common setup
    server_url, workspace_id, _, headers = get_request_setup()
    assembly = os.environ.get('GH_WORKSPACE_ASSEMBLY')

    if not assembly:
        raise ValueError("Missing required environment variable: GH_WORKSPACE_ASSEMBLY")

    # Construct the URL
    url = f"{server_url}/w/{workspace_id}/api/catalogs/source/{id}/createFromSystemTemplate"

    # Prepare payload
    payload = {
        "templateId": template_id,
        "name": name,
        "description": description,
        "group": group,
        "assembly": assembly,
        "approvalCount": approval_count
    }

    # Make the request
    response = requests.post(url, headers=headers, json=payload, verify=False)

    # Raise an exception for bad status codes
    if response.status_code >= 400:
        if response.status_code == 409:
            raise CatalogExistsError("Catalog already exists")
        raise requests.exceptions.HTTPError(f"HTTP {response.status_code}: {response.text}")

    return response.json()["id"]

def add_sample_fields(id: str, fields: list) -> dict:
    """
    Add sample fields to a catalog.

    Args:
        id (str): The ID of the catalog to add fields to
        fields (list): A list of fields to add to the catalog

    Returns:
        dict: The response from the API
    """
    # Get common setup
    server_url, workspace_id, _, headers = get_request_setup()

    # Construct the URL
    url = f"{server_url}/w/{workspace_id}/api/catalogs/template/?id=SampleCatalogExtended&format=JSON"

    # Make the request to get template schema
    response = requests.get(url, headers=headers, verify=False)

    # Raise an exception for bad status codes
    if response.status_code >= 400:
        raise requests.exceptions.HTTPError(f"HTTP {response.status_code}: {response.text}")

    # Parse the response text string and parse it as JSON
    template_data = json.loads(response.json()) # The result is a quoted string, but also needs to be parsed as JSON

    # Get the fields from the template
    template_fields = template_data.get('fields', [])

    # Get the schema for the existing catalog 'id'
    schema_url = f"{server_url}/w/{workspace_id}/api/catalogs/source/{id}/schema"
    schema_response = requests.get(schema_url, headers=headers, verify=False)

    # Raise an exception for bad status codes
    if schema_response.status_code >= 400:
        raise requests.exceptions.HTTPError(f"HTTP {schema_response.status_code}: {schema_response.text}")

    # Parse the schema response JSON
    schema_data = schema_response.json()
    existing_fields = schema_data.get('fields', [])

    # Find fields by name in the template fields list
    selected_fields = []
    for field in fields:
        # Search for field by name in template_fields list
        matching_field = next((f for f in template_fields if f.get('name') == field), None)
        if matching_field:
            # Check if field already exists in schema
            existing_field = next((f for f in existing_fields if f.get('name') == field), None)
            if existing_field:
                print(f"Field '{field}' already exists in catalog - skipping")
            else:
                matching_field['fId'] = -1 # Set fId to -1 to indicate a new field
                selected_fields.append(matching_field)
        else:
            print(f"Warning: Field '{field}' not found in template")
    if not selected_fields:
        print(f"All selected fields already exist in catalog '{id}'")
        return ''

    print(f"Adding the following fields to catalog '{id}':")
    for field in selected_fields:
        print(f"  - {field['name']}")

    # An updated field list for the schema (including existing fields)
    payload = {
        "fields": existing_fields + selected_fields,
        "note": f"Added fields: {', '.join(f['name'] for f in selected_fields)}"
    }
    # Make the request to add fields
    add_response = requests.put(schema_url, headers=headers, json=payload, verify=False)

    # Raise an exception for bad status codes
    if add_response.status_code >= 400:
        raise requests.exceptions.HTTPError(f"HTTP {add_response.status_code}: {add_response.text}")

    return add_response.json()

def create_gene_catalog(name: str) -> None:
    """
    Provision a per-build genomic gene catalog (GenePreferences or GeneLists) by invoking the
    `gautil creategenecatalog` command, which writes "<name>_<build>.catalog" into the workspace
    Catalogs directory using the same gacore engine the API server and desktop VarSeq use. This
    needs no running API server: gautil reads the shipped schema + TSV (GenePreferences is seeded
    with the shipped Golden Helix defaults) and looks coordinates up for the build from the gene
    source.

    The gautil binary is on PATH in the server task image; the workspace Catalogs directory is
    mounted at $WORKSPACE_DIR/Catalogs and the build comes from GH_WORKSPACE_ASSEMBLY. By default
    gautil resolves gene coordinates from the per-build RefSeqGenes track shipped in its system
    Data folder, so no downloaded annotations are required. The workspace's downloaded annotations
    folder (when present) and/or a remote repo (GH_GENE_SOURCE_URL, e.g. the public data repo) are
    passed as higher-priority sources, preferred when they cover the build. The command is
    idempotent: an already-present catalog for the build is left untouched.

    Args:
        name (str): "GenePreferences" or "GeneLists"
    """
    assembly = os.environ.get('GH_WORKSPACE_ASSEMBLY')
    if not assembly:
        raise ValueError("Missing required environment variable: GH_WORKSPACE_ASSEMBLY")

    workspace_dir = os.environ.get('WORKSPACE_DIR')
    if not workspace_dir:
        raise ValueError("Missing required environment variable: WORKSPACE_DIR")
    catalogs_dir = os.path.join(workspace_dir, 'Catalogs')

    gautil_bin = os.environ.get('GAUTIL_BIN', 'gautil')
    cmd = [gautil_bin, 'creategenecatalog', name, catalogs_dir, assembly]

    # GenePreferences defaults to an empty catalog; request the shipped Golden Helix content.
    # (GeneLists always seeds from the shipped list definitions.)
    if name == 'GenePreferences':
        cmd.append('--goldenHelixDefaults')

    # Point gautil at the build's gene source for coordinate lookup: the workspace's downloaded
    # annotations folder (when present) and/or a remote repo from GH_GENE_SOURCE_URL.
    annotations_dir = os.path.join(workspace_dir, 'AppData', 'Common Data', 'Annotations')
    if os.path.isdir(annotations_dir):
        cmd.append(f'--annotations={annotations_dir}')
    remote_source_url = os.environ.get('GH_GENE_SOURCE_URL')
    if remote_source_url:
        cmd.append(f'--remoteSourceUrl={remote_source_url}')

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"gautil creategenecatalog {name} failed with exit code {result.returncode}")

def main():
    parser = argparse.ArgumentParser(description='Create workspace catalogs')
    parser.add_argument('--create-sample', type=str, help='Create sample catalog (true/false)', default='false')
    parser.add_argument('--create-acmg', type=str, help='Create ACMG catalogs (true/false)', default='false')
    parser.add_argument('--create-amp', type=str, help='Create AMP catalogs (true/false)', default='false')
    parser.add_argument('--create-gene-list', type=str, help='Create Gene Lists catalog (true/false)', default='false')
    parser.add_argument('--create-gene-preferences', type=str, help='Create Gene Preferences catalog (true/false)', default='false')
    parser.add_argument('--add-sample-fields', type=str, help='Comma-separated list of additional fields to add')
    parser.add_argument('--sample-catalog-id', type=str, help='Target sample catalog ID (defaults to SampleCatalog)', default='SampleCatalog')
    parser.add_argument('--sample-catalog-name', type=str, help='Name for the sample catalog (defaults to "Sample Catalog")', default='Sample Catalog')
    parser.add_argument('--sample-catalog-description', type=str, help='Description for the sample catalog (defaults to "Default workspace sample catalog")', default='Default workspace sample catalog')

    args = parser.parse_args()

    # Convert string boolean values to actual booleans
    create_sample = args.create_sample.lower() == 'true'
    create_acmg = args.create_acmg.lower() == 'true'
    create_amp = args.create_amp.lower() == 'true'
    create_gene_list = args.create_gene_list.lower() == 'true'
    create_gene_preferences = args.create_gene_preferences.lower() == 'true'

    # Process sample fields if provided
    sample_fields = args.add_sample_fields.split(',') if args.add_sample_fields else []

    # Track if any errors occurred
    has_errors = False

    # Create sample catalog if requested
    if create_sample:
        try:
            result = create_catalog(
                id=args.sample_catalog_id,
                template_id="SampleCatalog",
                name=args.sample_catalog_name,
                description=args.sample_catalog_description,
                group="Sample"
            )
            print(f"Created sample catalog: {result}")
        except CatalogExistsError:
            print("Sample catalog already exists - skipping creation")
        except Exception as e:
            print(f"Error creating sample catalog: {e}", file=sys.stderr)
            print("Full traceback:", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            has_errors = True

    # If sample_fields is not empty, add them to the sample catalog
    if sample_fields:
        try:
            result = add_sample_fields(
                id=args.sample_catalog_id,
                fields=sample_fields
            )
        except Exception as e:
            print(f"Error adding fields to sample catalog: {str(e)}", file=sys.stderr)
            print("Full traceback:", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            has_errors = True

    # Create ACMG catalogs if requested
    if create_acmg:
        acmg_catalogs = [
            {
                "template_id": "ACMGCNVCaseCatalog",
                "name": "ACMG CNV Cases",
                "description": "ACMG CNV Case Catalog",
                "group": "VSClinical"
            },
            {
                "template_id": "ACMGCNVGeneCatalog",
                "name": "ACMG CNV Genes",
                "description": "ACMG CNV Gene Catalog",
                "group": "VSClinical"
            },
            {
                "template_id": "ACMGFusionCaseCatalog",
                "name": "ACMG Fusion Cases",
                "description": "ACMG Fusion Case Catalog",
                "group": "VSClinical"
            },
            {
                "template_id": "ACMGGuidelinesVariantAssessments",
                "name": "ACMG Variant Assessments",
                "description": "ACMG Guidelines Variant Assessments",
                "group": "VSClinical"
            }
        ]

        for catalog in acmg_catalogs:
            try:
                result = create_catalog(
                    id=catalog["template_id"],
                    template_id=catalog["template_id"],
                    name=catalog["name"],
                    description=catalog["description"],
                    group=catalog["group"]
                )
                print(f"Created ACMG catalog {catalog['name']}: {result}")
            except CatalogExistsError:
                print(f"ACMG catalog '{catalog['name']}' already exists - skipping creation")
            except Exception as e:
                print(f"Error creating ACMG catalog {catalog['name']}: {e}", file=sys.stderr)
                print("Full traceback:", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                has_errors = True

    # Create AMP catalogs if requested
    if create_amp:
        amp_catalogs = [
            {
                "template_id": "SomaticVariantsAssessments",
                "name": "Somatic Variant Cases",
                "description": "Somatic Variants Assessments",
                "group": "VSClinical"
            },
            {
                "template_id": "CancerInterpretation",
                "name": "Cancer Interpretations",
                "description": "Cancer Interpretations including genes, biomarkers, drug sensitivities, and more",
                "group": "VSClinical"
            },
            {
                "template_id": "DrugInterpretations",
                "name": "Drug Interpretations",
                "description": "Drug Interpretations",
                "group": "VSClinical"
            },
            {
                "template_id": "ACMGGuidelinesVariantAssessments",
                "name": "ACMG Variant Assessments",
                "description": "ACMG Guidelines Variant Assessments",
                "group": "VSClinical"
            }
        ]

        for catalog in amp_catalogs:
            try:
                result = create_catalog(
                    id=catalog["template_id"],
                    template_id=catalog["template_id"],
                    name=catalog["name"],
                    description=catalog["description"],
                    group=catalog["group"]
                )
                print(f"Created AMP catalog {catalog['name']}: {result}")
            except CatalogExistsError:
                print(f"AMP catalog '{catalog['name']}' already exists - skipping creation")
            except Exception as e:
                print(f"Error creating AMP catalog {catalog['name']}: {e}", file=sys.stderr)
                print("Full traceback:", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                has_errors = True

    # Create Gene Lists catalog if requested. Provisioned by gautil (per-build, genomic, with
    # looked-up coordinates) rather than the REST API, so no running API server is required.
    if create_gene_list:
        try:
            create_gene_catalog("GeneLists")
            print("Created Gene Lists catalog (or already present)")
        except Exception as e:
            print(f"Error creating Gene Lists catalog: {e}", file=sys.stderr)
            print("Full traceback:", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            has_errors = True

    # Create Gene Preferences catalog if requested. Provisioned by gautil (per-build, genomic,
    # seeded from the shipped Golden Helix defaults) rather than the REST API.
    if create_gene_preferences:
        try:
            create_gene_catalog("GenePreferences")
            print("Created Gene Preferences catalog (or already present)")
        except Exception as e:
            print(f"Error creating Gene Preferences catalog: {e}", file=sys.stderr)
            print("Full traceback:", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            has_errors = True

    # The gene catalogs are written to disk out-of-band by gautil, so the running API server will
    # not serve them (and clients' catalog pickers will not list them) until it re-scans. Trigger a
    # reload now that they exist.
    if create_gene_list or create_gene_preferences:
        try:
            reload_workspace_catalogs()
            print("Reloaded workspace catalogs on the API server")
        except Exception as e:
            print(f"Error reloading workspace catalogs: {e}", file=sys.stderr)
            print("Full traceback:", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            has_errors = True

    # Exit with error code if any errors occurred
    if has_errors:
        sys.exit(1)

if __name__ == "__main__":
    main()
