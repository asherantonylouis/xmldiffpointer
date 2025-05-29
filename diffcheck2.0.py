import xml.etree.ElementTree as ET
import csv
import mysql.connector

def get_all_xmls(connection, table_name, limit=15):
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT xml_content FROM {table_name} LIMIT {limit}")
        results = cursor.fetchall()
        return [row[0] for row in results], None
    except mysql.connector.Error as e:
        return None, f"MySQL error fetching from {table_name}: {e}"

def parse_xml_from_string(xml_string):
    try:
        root = ET.fromstring(xml_string)
        return root, None
    except ET.ParseError as e:
        return None, f"XML ParseError: {e}"

def flatten_elements(root):
    elements = {}
    def recurse(element):
        tag = element.tag
        if tag not in elements:
            elements[tag] = []
        elements[tag].append({
            "attrib": element.attrib,
            "text": (element.text or "").strip()
        })
        for child in element:
            recurse(child)
    recurse(root)
    return elements

def compare_xml(good_elements, bad_elements):
    differences = []

    # Compare tags and their indexed occurrences
    for tag in good_elements:
        good_items = good_elements[tag]
        bad_items = bad_elements.get(tag, [])

        for idx, good_item in enumerate(good_items):
            if idx >= len(bad_items):
                differences.append({
                    "Difference Type": "Tag missing",
                    "Tag Path": tag,
                    "Attribute": "-"
                })
                continue

            bad_item = bad_items[idx]
            good_attribs = good_item['attrib']
            bad_attribs = bad_item['attrib']

            for attr in good_attribs:
                if attr not in bad_attribs:
                    differences.append({
                        "Difference Type": "Attribute missing",
                        "Tag Path": tag,
                        "Attribute": attr
                    })
                elif good_attribs[attr] != bad_attribs[attr]:
                    differences.append({
                        "Difference Type": "Attribute mismatch",
                        "Tag Path": tag,
                        "Attribute": attr
                    })

            if good_item['text'] != bad_item['text']:
                differences.append({
                    "Difference Type": "Text mismatch",
                    "Tag Path": tag,
                    "Attribute": "(text)"
                })

    # Check for extra tags in bad_elements
    for tag in bad_elements:
        if tag not in good_elements:
            differences.append({
                "Difference Type": "Extra tag",
                "Tag Path": tag,
                "Attribute": "-"
            })

    return differences

from collections import defaultdict

def write_csv(all_differences, csv_file):
    fieldnames = ["Difference Type", "Tag Path", "Attribute", "Pair Indices"]

    # Group differences by (type, tag, attribute)
    grouped = defaultdict(set)

    for index, diffs in enumerate(all_differences, start=1):
        for diff in diffs:
            key = (
                diff["Difference Type"],
                diff["Tag Path"],
                diff["Attribute"]
            )
            grouped[key].add(index)

    # Write the deduplicated differences to CSV
    with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for (diff_type, tag_path, attribute), indices in grouped.items():
            writer.writerow({
                "Difference Type": diff_type,
                "Tag Path": tag_path,
                "Attribute": attribute,
                "Pair Indices": f"({', '.join(map(str, sorted(indices)))})"
            })

if __name__ == "__main__":
    connection = mysql.connector.connect(
        host="Localhost",
        user="root",
        password="KONOHA777",
        database="xml4"
    )

    # Get XMLs from both tables
    wcs_xmls, wcs_error = get_all_xmls(connection, "wcs")
    microservice_xmls, microservice_error = get_all_xmls(connection, "micro")

    all_differences = []

    if wcs_error or microservice_error:
        print("Error fetching data:", wcs_error or microservice_error)
    else:
        for i in range(min(len(wcs_xmls), len(microservice_xmls))):
            pair_diffs = []
            good_root, good_err = parse_xml_from_string(wcs_xmls[i])
            bad_root, bad_err = parse_xml_from_string(microservice_xmls[i])

            if good_err:
                pair_diffs.append({
                    "Difference Type": "Parse error",
                    "Tag Path": "wcs",
                    "Attribute": "-"
                })
            if bad_err:
                pair_diffs.append({
                    "Difference Type": "Parse error",
                    "Tag Path": "microservice",
                    "Attribute": "-"
                })

            if not good_err and not bad_err:
                good_elements = flatten_elements(good_root)
                bad_elements = flatten_elements(bad_root)
                pair_diffs.extend(compare_xml(good_elements, bad_elements))

            all_differences.append(pair_diffs)

    write_csv(all_differences, "diff15.csv")
    print("All differences written to diff15.csv")

    connection.close()