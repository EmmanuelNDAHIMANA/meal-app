"""
Single source of truth for every data table.

Each field is a dict:
    label  - exactly as it appears in the spec / Excel template header
    col    - MySQL column name
    sql    - MySQL column type
    ftype  - how to render & validate it
    req    - required?

ftype values:
    text, textarea, int, decimal, date, phone, gps, link
    gender, youth
    project
    implementer, intervention          (cascading pair)
    district, sector, cell, village    (cascading chain)
    tree_origin, tree_type, tree_species (cascading chain, optional ref file)
"""


def f(label, col, sql, ftype, req=False, options=None):
    d = {"label": label, "col": col, "sql": sql, "ftype": ftype, "req": req}
    if options:
        d["options"] = options
    return d


PROJECT = f("Project", "project", "VARCHAR(50)", "project", True)
IMPLEMENTER = f("Implementer", "implementer", "VARCHAR(150)", "implementer", True)
INTERVENTION = f("Intervention", "intervention", "VARCHAR(255)", "intervention", True)

DISTRICT = f("District", "district", "VARCHAR(100)", "district", True)
SECTOR = f("Sector", "sector", "VARCHAR(100)", "sector", True)
CELL = f("Cell", "cell", "VARCHAR(100)", "cell", True)
VILLAGE = f("Village", "village", "VARCHAR(100)", "village")

TREE_ORIGIN = f("Tree Orgine", "tree_origin", "VARCHAR(100)", "tree_origin")
TREE_TYPE = f("Tree Type", "tree_type", "VARCHAR(100)", "tree_type")
TREE_SPECIES = f("Tree species", "tree_species", "VARCHAR(150)", "tree_species")


TABLES = {
    # ------------------------------------------------------------------
    "tree_plantation": {
        "table": "tree_plantation",
        "title": "Tree Plantation",
        "icon": "🌳",
        "fields": [
            PROJECT, IMPLEMENTER, INTERVENTION,
            f("Year", "year", "INT", "int", True),
            f("Site Name", "site_name", "VARCHAR(255)", "text", True),
            f("Area(Ha)", "area_ha", "DECIMAL(14,4)", "decimal"),
            DISTRICT,
            f("Sector", "sector", "VARCHAR(100)", "sector"),
            f("Cell", "cell", "VARCHAR(100)", "cell"),
            f("Shapefile", "shapefile", "VARCHAR(500)", "file"),
            f("Tree Category", "tree_category", "VARCHAR(100)", "tree_origin"),
            TREE_TYPE, TREE_SPECIES,
            f("Number of trees Planted", "num_trees_planted", "INT", "int"),
            f("Number of trees (Baseline)", "num_trees_baseline", "INT", "int"),
            f("Trees density (Number per Ha)", "trees_density", "DECIMAL(14,4)", "decimal"),
            f("Areas requiring replanting (km)", "area_replanting_km", "DECIMAL(14,4)", "decimal"),
            f("Replacement date", "replacement_date", "DATE", "date"),
            f("Number of Trees replanted", "num_trees_replanted", "INT", "int"),
            f("Block leader (Names)", "block_leader", "VARCHAR(150)", "text"),
            f("Phone number", "phone_number", "VARCHAR(30)", "phone"),
            f("Location (GPS)", "location_gps", "VARCHAR(120)", "gps"),
        ],
    },
    # ------------------------------------------------------------------
    "beneficiaries": {
        "table": "beneficiaries",
        "title": "Beneficiaries",
        "icon": "👥",
        "fields": [
            PROJECT, IMPLEMENTER, INTERVENTION,
            f("Intervention Year", "intervention_year", "INT", "int"),
            f("Activity Code", "activity_code", "VARCHAR(50)", "text"),
            f("Date", "record_date", "DATE", "date", True),
            f("Name of Beneficiary", "beneficiary_name", "VARCHAR(150)", "text", True),
            f("Gender", "gender", "VARCHAR(20)", "gender"),
            f("Phone Number", "phone_number", "VARCHAR(30)", "phone"),
            f("ID No.", "id_no", "VARCHAR(50)", "text"),
            DISTRICT, SECTOR, CELL, VILLAGE,
            f("Number of persons in HH", "persons_in_hh", "INT", "int"),
            f("Beneficiary Category", "beneficiary_category", "VARCHAR(150)", "choice",
              options=["Direct", "Indirect"]),
        ],
    },
    # ------------------------------------------------------------------
    "bso": {
        "table": "bso",
        "title": "BSO",
        "icon": "🐝",
        "fields": [
            PROJECT, IMPLEMENTER, INTERVENTION,
            f("Site name", "site_name", "VARCHAR(255)", "text", True),
            f("Area(ha)", "area_ha", "DECIMAL(14,4)", "decimal"),
            DISTRICT, SECTOR, CELL, VILLAGE,
            f("Shape file", "shapefile", "VARCHAR(500)", "file"),
            f("Year of Plantation", "year_of_plantation", "INT", "int"),
            TREE_ORIGIN, TREE_TYPE, TREE_SPECIES,
            f("Number of Tree planted for each species", "num_trees_planted", "INT", "int"),
            f("Trees density (Number per Ha)", "trees_density", "DECIMAL(14,4)", "decimal"),
            f("Species for Replacement", "species_replacement", "VARCHAR(150)", "text"),
            f("Areas requiring replanting (ha)", "area_replanting_ha", "DECIMAL(14,4)", "decimal"),
            f("Replacement date", "replacement_date", "DATE", "date"),
            f("Number of Trees replanted", "num_trees_replanted", "INT", "int"),
            f("Location(GPS Coordinate)", "location_gps", "VARCHAR(120)", "gps"),
        ],
    },
    # ------------------------------------------------------------------
    "silvo": {
        "table": "silvo",
        "title": "Silvo",
        "icon": "🐄",
        "fields": [
            PROJECT, IMPLEMENTER, INTERVENTION,
            f("Owner's Name (Invidual/FFS/Group)", "owner_name", "VARCHAR(200)", "text", True),
            f("Phone number", "phone_number", "VARCHAR(30)", "phone"),
            f("Area(ha)", "area_ha", "DECIMAL(14,4)", "decimal"),
            DISTRICT, SECTOR, CELL, VILLAGE,
            f("Shape file", "shapefile", "VARCHAR(500)", "file"),
            f("Year of Plantation", "year_of_plantation", "INT", "int"),
            TREE_ORIGIN, TREE_TYPE, TREE_SPECIES,
            f("Number of Tree planted for each species", "num_trees_planted", "INT", "int"),
            f("Number of Survived Trees", "num_survived_trees", "INT", "int"),
            f("Survival Evaluation Date", "survival_eval_date", "DATE", "date"),
            f("Trees density (Number per Ha)", "trees_density", "DECIMAL(14,4)", "decimal"),
            f("Location", "location_gps", "VARCHAR(120)", "gps"),
        ],
    },
    # ------------------------------------------------------------------
    "af_demo": {
        "table": "af_demo",
        "title": "AF-Demo",
        "icon": "🌿",
        "fields": [
            PROJECT, IMPLEMENTER, INTERVENTION,
            f("Site Name", "site_name", "VARCHAR(255)", "text", True),
            f("Owner's Name (Invidual/FFS/Group)", "owner_name", "VARCHAR(200)", "text"),
            f("Phone number", "phone_number", "VARCHAR(30)", "phone"),
            f("Area(ha)", "area_ha", "DECIMAL(14,4)", "decimal"),
            DISTRICT, SECTOR, CELL, VILLAGE,
            f("Shape file", "shapefile", "VARCHAR(500)", "file"),
            f("Year of Plantation", "year_of_plantation", "INT", "int"),
            TREE_ORIGIN, TREE_TYPE, TREE_SPECIES,
            f("Number of Tree planted for each species", "num_trees_planted", "INT", "int"),
            f("Number of Survived Trees", "num_survived_trees", "INT", "int"),
            f("Survival Evaluation Date", "survival_eval_date", "DATE", "date"),
            f("Trees density (Number per Ha)", "trees_density", "DECIMAL(14,4)", "decimal"),
            f("Location", "location_gps", "VARCHAR(120)", "gps"),
        ],
    },
    # ------------------------------------------------------------------
    "activities": {
        "table": "activities",
        "title": "Activities",
        "icon": "📋",
        "fields": [
            PROJECT, IMPLEMENTER,
            f("Main Activity", "main_activity", "VARCHAR(255)", "text", True),
            f("Sub Activity", "sub_activity", "VARCHAR(255)", "text"),
            f("Deliverables", "deliverables", "TEXT", "textarea"),
            f("StartDate", "start_date", "DATE", "date"),
            f("EndDate", "end_date", "DATE", "date"),
            f("Reporting Date", "reporting_date", "DATE", "date"),
            f("Execution Progress", "execution_progress", "VARCHAR(100)", "text"),
            f("Comments", "comments", "TEXT", "textarea"),
            f("Expected Results", "expected_results", "TEXT", "textarea"),
        ],
    },
    # ------------------------------------------------------------------
    "indicators": {
        "table": "indicators",
        "title": "Indicators",
        "icon": "📊",
        "fields": [
            PROJECT, IMPLEMENTER,
            f("Activity reference", "activity_reference", "VARCHAR(150)", "text"),
            f("Indicator", "indicator", "VARCHAR(500)", "text", True),
            f("Sub Indicator", "sub_indicator", "VARCHAR(500)", "text"),
            f("Unit", "unit", "VARCHAR(50)", "choice",
              options=["Number", "Hectares", "tCO2eq", "USD", "%", "Tree/hectare"]),
            f("Mid-Term Target", "mid_term_target", "DECIMAL(18,4)", "decimal"),
            f("LoP Target", "lop_target", "DECIMAL(18,4)", "decimal"),
            f("Reporting Date", "reporting_date", "DATE", "date", True),
            f("Target/Year", "target_year", "DECIMAL(18,4)", "decimal"),
            f("Actual Value", "actual_value", "DECIMAL(18,4)", "decimal"),
            f("Indicator Type", "indicator_type", "VARCHAR(100)", "choice",
              options=["Output", "Outcome", "Impact"]),
        ],
    },
    # ------------------------------------------------------------------
    "trainings": {
        "table": "trainings",
        "title": "Trainings",
        "icon": "🎓",
        "fields": [
            PROJECT, IMPLEMENTER,
            f("Training Description", "training_description", "TEXT", "textarea", True),
            f("Site name(where training took place)", "site_name", "VARCHAR(255)", "text"),
            f("Start Date", "start_date", "DATE", "date"),
            f("End Date", "end_date", "DATE", "date"),
            f("Activity code", "activity_code", "VARCHAR(50)", "text"),
            f("Beneficiaries Category", "beneficiaries_category", "VARCHAR(150)", "choice",
              options=["Farmer", "Gov", "Priv"]),
            f("Number of Participants", "num_participants", "INT", "int"),
            f("Gender", "gender", "VARCHAR(20)", "gender"),
            f("Age_Group", "age_group", "VARCHAR(50)", "choice",
              options=["Adult", "Youth"]),
            f("Attach Training Modules/ Reports(pdf or word)", "modules_link", "VARCHAR(500)", "file"),
            f("Link to attendance Lists(pdf or jpeg)", "attendance_link", "VARCHAR(500)", "file"),
            f("Remarks", "remarks", "TEXT", "textarea"),
        ],
    },
    # ------------------------------------------------------------------
    "jobs_created": {
        "table": "jobs_created",
        "title": "Jobs Created",
        "icon": "💼",
        "fields": [
            PROJECT, IMPLEMENTER, INTERVENTION,
            f("Jobs created Year", "jobs_created_year", "INT", "int"),
            f("Activity code", "activity_code", "VARCHAR(50)", "text"),
            f("Cooperative membership", "cooperative_membership", "VARCHAR(100)", "choice",
              options=["Yes", "No"]),
            f("Name of Cooperative/Group", "cooperative_name", "VARCHAR(200)", "text"),
            f("Beneficiary Names", "beneficiary_names", "VARCHAR(200)", "text", True),
            f("Gender (Male &Female)", "gender", "VARCHAR(20)", "gender"),
            f("ID No.", "id_no", "VARCHAR(50)", "text"),
            f("Phone Number", "phone_number", "VARCHAR(30)", "phone"),
            f("Youth or Not Youth", "youth_status", "VARCHAR(20)", "youth"),
            f("Education Level", "education_level", "VARCHAR(100)", "choice",
              options=["None and Primary", "Secondary", "University"]),
            f("Types of jobs done", "job_type", "VARCHAR(200)", "text"),
            f("Employment Contract", "employment_contract", "VARCHAR(100)", "choice",
              options=["Yes", "No"]),
            f("Start date (Month, year)", "start_date", "DATE", "date"),
            DISTRICT, SECTOR, CELL,
        ],
    },
    # ------------------------------------------------------------------
    "roadsides": {
        "table": "roadsides",
        "title": "Roadsides",
        "icon": "🛣️",
        "fields": [
            PROJECT, IMPLEMENTER,
            f("Intervetion", "intervention", "VARCHAR(255)", "intervention", True),
            DISTRICT,
            f("Road Name", "road_name", "VARCHAR(255)", "text", True),
            f("Road Type", "road_type", "VARCHAR(100)", "text"),
            f("Length (Km)", "length_km", "DECIMAL(14,4)", "decimal"),
            f("Year restored", "year_restored", "INT", "int"),
            f("Shapefile", "shapefile", "VARCHAR(500)", "file"),
            f("Tree Category", "tree_category", "VARCHAR(100)", "tree_origin"),
            TREE_TYPE, TREE_SPECIES,
            f("Number of Trees", "num_trees", "INT", "int"),
            f("Location", "location", "VARCHAR(120)", "gps"),
            f("Area requiring replanting (km)", "area_replanting_km", "DECIMAL(14,4)", "decimal"),
            f("Replanting date", "replanting_date", "DATE", "date"),
            f("Number of Trees Replanted", "num_trees_replanted", "INT", "int"),
            f("CVC operational ?", "cvc_operational", "VARCHAR(10)", "choice", options=["Yes", "No"]),
            f("Number of CVCs", "num_cvcs", "INT", "int"),
            f("CVC Members Male", "cvc_members_male", "INT", "int"),
            f("CVC Members Female", "cvc_members_female", "INT", "int"),
            f("Attachments of CVC memebers", "cvc_members_attachments", "VARCHAR(500)", "file"),
        ],
    },
}

TABLE_ORDER = [
    "tree_plantation", "beneficiaries", "bso", "silvo", "af_demo",
    "activities", "indicators", "trainings", "jobs_created", "roadsides",
]

AUDIT_COLS = ["created_by", "created_at", "source"]


def labels(table_key: str) -> list[str]:
    return [fl["label"] for fl in TABLES[table_key]["fields"]]


def columns(table_key: str) -> list[str]:
    return [fl["col"] for fl in TABLES[table_key]["fields"]]
