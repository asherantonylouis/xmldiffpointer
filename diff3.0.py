import xml.etree.ElementTree as ET
import csv
import mysql.connector
from collections import defaultdict

def get_xml_by_order_id(connection, order_id):
    try:
        cursor = connection.cursor()
        query = "SELECT xml_content FROM orders WHERE order_id = %s"
        cursor.execute(query, (order_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except mysql.connector.Error as e:
        return None

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

    for tag in bad_elements:
        if tag not in good_elements:
            differences.append({
                "Difference Type": "Extra tag",
                "Tag Path": tag,
                "Attribute": "-"
            })

    return differences

def write_csv(all_differences, csv_file):
    fieldnames = ["Difference Type", "Tag Path", "Attribute", "Order Pair"]
    with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pair_id, diffs in all_differences:
            for diff in diffs:
                writer.writerow({
                    "Difference Type": diff["Difference Type"],
                    "Tag Path": diff["Tag Path"],
                    "Attribute": diff["Attribute"],
                    "Order Pair": pair_id
                })

def read_order_pairs(csv_filename):
    with open(csv_filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        return [(row['wcs_order_id'], row['micro_order_id']) for row in reader]

if __name__ == "__main__":
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="KONOHA777",
        database="checks"
    )

    order_pairs = read_order_pairs("orders_to_compare.csv")
    all_differences = []

    for wcs_id, micro_id in order_pairs:
        wcs_xml = get_xml_by_order_id(connection, wcs_id)
        micro_xml = get_xml_by_order_id(connection, micro_id)
        pair_label = f"{wcs_id}-{micro_id}"

        pair_diffs = []

        if not wcs_xml or not micro_xml:
            pair_diffs.append({
                "Difference Type": "Missing XML",
                "Tag Path": "N/A",
                "Attribute": f"Missing for {'WCS' if not wcs_xml else 'Micro'}"
            })
            all_differences.append((pair_label, pair_diffs))
            continue

        good_root, good_err = parse_xml_from_string(wcs_xml)
        bad_root, bad_err = parse_xml_from_string(micro_xml)

        if good_err:
            pair_diffs.append({
                "Difference Type": "Parse error",
                "Tag Path": "WCS",
                "Attribute": good_err
            })
        if bad_err:
            pair_diffs.append({
                "Difference Type": "Parse error",
                "Tag Path": "Micro",
                "Attribute": bad_err
            })

        if not good_err and not bad_err:
            good_elements = flatten_elements(good_root)
            bad_elements = flatten_elements(bad_root)
            pair_diffs.extend(compare_xml(good_elements, bad_elements))

        all_differences.append((pair_label, pair_diffs))

    write_csv(all_differences, "order_comapare_xml_differences.csv")
    print("Differences saved to 'order_comapare_xml_differences.csv'")
    connection.close()