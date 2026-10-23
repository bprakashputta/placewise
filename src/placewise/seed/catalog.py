"""Reference data for synthetic A/E/C candidates.

All people are fake. Employer names are real A/E/C firms, used only to make test
resumes realistic. Every generated record is marked synthetic, roles are ordinary,
and nothing specific or negative is claimed about any firm.
"""

DISCIPLINE_WEIGHTS = {
    "architecture": 18,
    "interior_design": 12,
    "civil": 20,
    "structural": 12,
    "mep": 15,
    "construction_management": 23,
}

# Metro → (weight, [(city, state)])
METROS = {
    "DFW": (60, [("Dallas", "TX"), ("Fort Worth", "TX"), ("Plano", "TX"), ("Frisco", "TX"), ("Irving", "TX"),
                 ("Arlington", "TX"), ("Richardson", "TX"), ("McKinney", "TX"), ("Southlake", "TX"),
                 ("Denton", "TX"), ("Grapevine", "TX"), ("Carrollton", "TX")]),
    "Houston": (14, [("Houston", "TX"), ("Sugar Land", "TX"), ("The Woodlands", "TX"), ("Katy", "TX")]),
    "Austin": (12, [("Austin", "TX"), ("Round Rock", "TX"), ("Georgetown", "TX")]),
    "San Antonio": (8, [("San Antonio", "TX"), ("New Braunfels", "TX")]),
    "Other": (6, [("Oklahoma City", "OK"), ("Tulsa", "OK"), ("Shreveport", "LA"), ("Baton Rouge", "LA"),
                  ("Little Rock", "AR"), ("Denver", "CO"), ("Phoenix", "AZ"), ("Atlanta", "GA")]),
}

# Career levels by years of experience: (max_years, level_index)
LEVELS = [(2, 0), (6, 1), (12, 2), (20, 3), (99, 4)]

TITLES = {
    "architecture": ["Architectural Designer", "Project Architect", "Senior Project Architect",
                     "Associate / Project Manager", "Principal"],
    "interior_design": ["Junior Interior Designer", "Interior Designer", "Senior Interior Designer",
                        "Project Designer", "Design Director"],
    "civil": ["Civil Engineer in Training", "Project Engineer", "Senior Project Engineer",
              "Project Manager", "Senior Project Manager"],
    "structural": ["Structural Engineer in Training", "Structural Engineer", "Senior Structural Engineer",
                   "Structural Project Manager", "Principal"],
    "mep": ["{sub} Designer", "{sub} Project Engineer", "Senior {sub} Engineer",
            "{sub} Engineering Project Manager", "{sub} Engineering Principal"],
    "construction_management": ["Project Engineer", "Assistant Project Manager", "Project Manager",
                                "Senior Project Manager", "Project Executive"],
}
# Alternative construction career track (field side)
CM_FIELD_TITLES = ["Field Engineer", "Assistant Superintendent", "Superintendent",
                   "Senior Superintendent", "General Superintendent"]
CM_ESTIMATING_TITLES = ["Estimator I", "Estimator", "Senior Estimator", "Chief Estimator",
                        "Director of Preconstruction"]

SUBDISCIPLINES = {
    "civil": ["transportation", "land development", "water/wastewater", "drainage", "municipal"],
    "mep": ["Mechanical", "Electrical", "Plumbing"],
    "construction_management": ["project management", "field operations", "estimating"],
}

SOFTWARE = {
    "architecture": ["Revit", "AutoCAD", "Rhino", "SketchUp", "Enscape", "Bluebeam Revu", "Adobe Creative Suite",
                     "Navisworks", "Lumion", "Grasshopper"],
    "interior_design": ["Revit", "AutoCAD", "SketchUp", "Enscape", "Adobe Creative Suite", "Bluebeam Revu",
                        "V-Ray", "Microsoft Excel"],
    "civil": ["Civil 3D", "AutoCAD", "MicroStation", "OpenRoads Designer", "HEC-RAS", "HEC-HMS", "StormCAD",
              "ArcGIS", "Bluebeam Revu", "GEOPAK"],
    "structural": ["ETABS", "SAP2000", "RISA-3D", "RAM Structural System", "Tekla Structures", "Revit", "SAFE",
                   "Enercalc", "AutoCAD"],
    "mep": ["Revit MEP", "AutoCAD MEP", "Trane TRACE 3D Plus", "Carrier HAP", "SKM PowerTools", "ETAP",
            "AGi32", "Navisworks", "Bluebeam Revu"],
    "construction_management": ["Procore", "Primavera P6", "Microsoft Project", "Bluebeam Revu",
                                "Autodesk Construction Cloud", "Sage 300 CRE", "On-Screen Takeoff",
                                "PlanGrid", "Navisworks"],
}

SECTORS = {
    "architecture": ["healthcare", "K-12 education", "higher education", "commercial office", "hospitality",
                     "multifamily", "civic", "mixed-use", "sports and entertainment"],
    "interior_design": ["corporate workplace", "hospitality", "healthcare", "multifamily", "retail",
                        "higher education", "senior living"],
    "civil": ["transportation", "land development", "water/wastewater", "drainage and flood control",
              "municipal infrastructure", "aviation"],
    "structural": ["commercial office", "healthcare", "K-12 education", "parking structures", "industrial",
                   "sports and entertainment", "multifamily"],
    "mep": ["healthcare", "mission critical / data centers", "K-12 education", "higher education",
            "commercial office", "industrial", "laboratories"],
    "construction_management": ["commercial office", "healthcare", "K-12 education", "multifamily",
                                "industrial", "mission critical / data centers", "hospitality", "civic"],
}

FIRMS = {
    "architecture": ["HKS", "Corgan", "Gensler", "Perkins&Will", "Page", "PGAL", "GFF", "Huckabee", "HOK",
                     "Stantec", "BOKA Powell", "Overland Partners", "Lake|Flato", "SmithGroup"],
    "interior_design": ["Gensler", "HKS", "Corgan", "Perkins&Will", "Staffelbach", "Stantec", "HOK", "Page"],
    "civil": ["Kimley-Horn", "Halff", "Freese and Nichols", "Huitt-Zollars", "Garver",
              "Lockwood, Andrews & Newnam", "Pape-Dawson", "Teague Nall and Perkins", "BGE", "Dunaway",
              "HDR", "Jacobs", "AECOM", "Stantec", "WSP", "Burns & McDonnell"],
    "structural": ["Walter P Moore", "Datum Engineers", "Thornton Tomasetti", "JQ Engineering", "Stantec",
                   "WSP", "HKS"],
    "mep": ["Burns & McDonnell", "IMEG", "Henderson Engineers", "Smith Seckman Reid", "WSP", "Stantec",
            "Jacobs", "Salas O'Brien", "CCRD"],
    "construction_management": ["Turner Construction", "Balfour Beatty", "McCarthy Building Companies",
                                "Hensel Phelps", "Austin Commercial", "Manhattan Construction", "Skanska",
                                "DPR Construction", "Rogers-O'Brien Construction", "The Beck Group", "JE Dunn",
                                "Whiting-Turner", "Hill & Wilkinson"],
}

UNIVERSITIES = {
    "TX": ["University of Texas at Arlington", "University of Texas at Austin", "Texas A&M University",
           "Texas Tech University", "University of Houston", "University of Texas at San Antonio",
           "University of North Texas", "Prairie View A&M University", "Southern Methodist University",
           "Baylor University", "Rice University"],
    "other": ["Oklahoma State University", "University of Oklahoma", "Louisiana State University",
              "Kansas State University", "Arizona State University", "University of Arkansas",
              "Georgia Institute of Technology", "University of Colorado Boulder"],
}

DEGREES = {
    "architecture": [("Bachelor of Architecture", None), ("Master of Architecture", None),
                     ("B.S. in Architectural Studies", None)],
    "interior_design": [("B.F.A. in Interior Design", None), ("B.S. in Interior Design", None)],
    "civil": [("B.S. in Civil Engineering", None), ("M.S. in Civil Engineering", None)],
    "structural": [("B.S. in Civil Engineering", None), ("M.S. in Structural Engineering", None),
                   ("B.S. in Architectural Engineering", None)],
    "mep": [("B.S. in Mechanical Engineering", "Mechanical"), ("B.S. in Electrical Engineering", "Electrical"),
            ("B.S. in Architectural Engineering", None)],
    "construction_management": [("B.S. in Construction Science", None), ("B.S. in Construction Management", None),
                                ("B.S. in Civil Engineering", None), ("B.B.A. in Business Administration", None)],
}

# Salary ranges (USD) by level index, for a realistic "desired salary"
SALARY_BY_LEVEL = [(62_000, 78_000), (78_000, 105_000), (100_000, 140_000), (130_000, 180_000),
                   (170_000, 240_000)]

PROJECT_TYPES = {
    "healthcare": ["Regional Medical Center Expansion", "Outpatient Clinic", "Hospital Bed Tower",
                   "Medical Office Building"],
    "K-12 education": ["ISD Middle School", "ISD High School Addition", "Elementary School Replacement"],
    "higher education": ["University Science Building", "Student Housing", "Campus Recreation Center"],
    "commercial office": ["Corporate Headquarters", "Class A Office Tower", "Office Interior Renovation"],
    "corporate workplace": ["Corporate Headquarters Interiors", "Office Relocation", "Workplace Refresh"],
    "hospitality": ["Hotel Renovation", "Resort Expansion", "Boutique Hotel"],
    "multifamily": ["Mixed-Use Apartments", "Garden-Style Apartments", "Mid-Rise Residential"],
    "retail": ["Flagship Retail Store", "Shopping Center Renovation"],
    "senior living": ["Senior Living Community"],
    "civic": ["City Hall", "Public Library", "Fire Station"],
    "mixed-use": ["Mixed-Use Development"],
    "sports and entertainment": ["Stadium Renovation", "Arena Club Level", "Performing Arts Center"],
    "transportation": ["Highway Widening", "Interchange Reconstruction", "Thoroughfare Improvements",
                       "Bridge Replacement"],
    "land development": ["Residential Subdivision", "Master-Planned Community", "Commercial Site Development"],
    "water/wastewater": ["Water Treatment Plant Expansion", "Wastewater Lift Station", "Water Line Replacement"],
    "drainage and flood control": ["Drainage Improvements", "Detention Pond", "Channel Improvements"],
    "municipal infrastructure": ["Street Reconstruction", "Downtown Streetscape"],
    "aviation": ["Airport Taxiway Rehabilitation", "Airport Apron Expansion"],
    "parking structures": ["Parking Garage"],
    "industrial": ["Distribution Center", "Manufacturing Facility"],
    "mission critical / data centers": ["Data Center Campus", "Data Center Hall Fit-Out"],
    "laboratories": ["Research Laboratory Building"],
}
