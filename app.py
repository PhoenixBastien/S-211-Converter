import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import Tk, IntVar, StringVar, filedialog, ttk
from urllib.parse import urlparse, parse_qs, quote_plus
 
import chardet
import pandas as pd
 
# global dict of each field name and its corresponding tag number
field_dict = {
    'Main Entry Corporate Name': '110',
    'Title Statement': '245',
    'Varying Form of Title': '246',
    'Edition Statement': '250',
    'Publication, Distrbution': '260',
    'Projected Publication Date': '263',
    'Publisher Tag': '269',
    'Physical Description': '300',
    'Series Statement': '490',
    'General Notes': '500',
    'Subject': '650',
    'Corporate Name': '710',
    'Series Name': '800',
    'URL': '856'
}
 
# inverse of field_dict
tag_dict = {
    field_dict[field_name]: field_name
    for field_name in field_dict
}
 
def xml_to_csv(xml_path: Path | str) -> None:
    '''Convert xml file to csv'''
 
    # parse xml file into element tree and get root element of tree
    root = ET.parse(xml_path).getroot()
    # define namespace of tree
    namespaces = {'xmlns': 'http://www.loc.gov/MARC21/slim'}
    # initialize empty data list of records
    data = []
 
    # iterate over each record in the tree
    for record in root:
        # initialize defaultdict of record where each field is a list (auto-assigns a default value for nonexistent keys to avoid KeyErrors)
        record_dict = defaultdict(list)
 
        # get and add leader to dict
        leader = record.find('.//xmlns:leader', namespaces)
        record_dict['Leader'].append(leader.text.strip())
 
        # iterate over each controlfield in the record
        for controlfield in record.findall('.//xmlns:controlfield', namespaces):
            # get controlfield tag number and text
            tag = controlfield.attrib['tag']
            text = (controlfield.text or '').strip()
 
            if tag == '005':
                # parse and format timestamp and format according to iso
                timestamp = datetime.strptime(text, '%Y%m%d%H%M%S.0')
                text = timestamp.isoformat()
 
            # add controlfield to dict
            record_dict[f'controlfield {tag}'].append(text)
 
        # iterate over each datafield in the record
        for datafield in record.findall('.//xmlns:datafield', namespaces):
            # get datafield tag number and text
            tag = datafield.attrib['tag']
            subfields = datafield.findall('.//xmlns:subfield', namespaces)
 
            # skip to next iteration if field is unknown
            if tag not in field_dict.values():
                continue
           
            if tag == '260': # Publication, Distrbution
                # get text of subfields and use empty string if empty
                publication = (subfields[0].text or '').strip()
                distribution = (subfields[1].text or '').strip()
                # join publication and distribution separated by newline
                text = f'{publication}\n{distribution}'.strip()
            elif tag == '710': # Corporate Name
                # get text of subfield and replace '|' with newlines and use empty string if empty
                text = (subfields[0].text or '').strip().replace('|', '\n')
            elif tag == '856': # URL
                # get link location and display text
                link_location = subfields[0].text.strip()
                display_text = quote_plus(subfields[1].text.strip())
                text = f'{link_location}?display_text={display_text}'
            else:
                # get text of subfield and use empty string if empty
                text = (subfields[0].text or '').strip()
           
            # get field name based on tag number and add text to record's respective field
            field_name = tag_dict[tag]
            record_dict[field_name].append(text)
       
        # add record to data list
        data.append(record_dict)
   
    # convert data list to dataframe, fill na values with empty strings and convert lists into string where each element is separated by two newlines
    df = pd.DataFrame(data).fillna('').map(lambda x: '\n\n'.join(x))
 
    # write dataframe to csv file with signed utf-8 encoding to avoid any errors
    csv_path = Path.home() / 'Downloads' / f'{Path(xml_path).stem}.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    return csv_path
    # print(f'xml converted to csv at {csv_path}')
 
def csv_to_xml(csv_path: Path | str) -> None:
    '''Convert csv file to xml'''
 
    # detect encoding of csv file
    with open(csv_path, 'rb') as f:
        encoding = chardet.detect(f.read())['encoding']
 
    # read csv file into dataframe with encoding detected above, set empty values to empty strings, and convert all values to strings
    df = pd.read_csv(csv_path, encoding=encoding, keep_default_na=False).astype(str)
   
    # define root of tree as collection and define tree based on root
    root = ET.Element('collection', xmlns='http://www.loc.gov/MARC21/slim')
    tree = ET.ElementTree(root)
 
    # iterate over rows of dataframe
    for _, row in df.iterrows():
        # define record as subelement of root
        record = ET.SubElement(root, 'record')
 
        # iterate over columns of dataframe
        for field_name in df.columns:
            # get cell based on field name and split string with 2+ newlines into individual elements in a list
            cell = re.split('\n{2,}', row[field_name])
 
            # iterate over text in cell
            for text in cell:
                # skip iteration if string is empty
                if not text:
                    continue
                   
                if field_name.lower() == 'leader': # leader
                    # define leader as subelement of record and set its text
                    leader = ET.SubElement(record, 'leader')
                    leader.text = text.strip()
                elif field_name.startswith('controlfield'): # controlfield
                    # get controlfield tag number
                    tag = field_name.replace('controlfield', '').strip()
 
                    if tag == '005':
                        # get timestamp from string in iso format and format as long number
                        timestamp = datetime.fromisoformat(text)
                        text = timestamp.strftime('%Y%m%d%H%M%S.0')
 
                    # define controlfield as subelement of record with its corresponding tag number as an attribute and set its text
                    controlfield = ET.SubElement(record, 'controlfield', tag=tag)
                    controlfield.text = text.strip()
                elif field_name == 'ID': # delete file
                    controlfield = ET.SubElement(record, 'controlfield', tag='001')
                    controlfield.text = text.strip()
                else: # datafield
                    # skip to next iteration if field name is unknown
                    if field_name not in field_dict:
                        continue
                   
                    # get datafield tag number and define datafield as subelement of record with its corresponding tag number as an attribute
                    tag = field_dict[field_name]
                    datafield = ET.SubElement(record, 'datafield', tag=tag)
 
                    if tag == '260': # Publication, Distrbution
                        # define first and second subfields as subelements of datafield with codes 'a' and 'b' respectively
                        subfield1 = ET.SubElement(datafield, 'subfield', code='a')
                        subfield2 = ET.SubElement(datafield, 'subfield', code='b')
 
                        # split text by newline and set text of first subfield
                        split_text = text.strip().split('\n')
                        subfield1.text = split_text[0].strip()
 
                        # set text of second subfield if it exists
                        if len(split_text) == 2:
                            subfield2.text = split_text[1].strip()
                    elif tag == '710': # Corporate Name
                        # define subfield as subelement of datafield with code 'a' and set its text with newlines replaced with '|'
                        subfield = ET.SubElement(datafield, 'subfield', code='a')
                        subfield.text = text.strip().replace('\n', '|').strip()
                    elif tag == '856': # URL
                        # define first (link location) and second subfields (display text) as subelements of datafield with with codes 'u' and 'y' respectively
                        subfield1 = ET.SubElement(datafield, 'subfield', code='u')
                        subfield2 = ET.SubElement(datafield, 'subfield', code='y')
 
                        # parse url and query
                        parsed_url = urlparse(text)
                        parsed_query = parse_qs(parsed_url.query)
 
                        # get link location from parsed url without query
                        link_location = parsed_url._replace(query='').geturl()
 
                        # get display text from parsed query if it exists or default to 'Online access'
                        if 'display_text' in parsed_query:
                            display_text = parsed_query['display_text'][0]
                        else:
                            display_text = 'Online access'
 
                        # set text of subfields
                        subfield1.text = link_location.strip()
                        subfield2.text = display_text.strip()
                    else:
                        # define subfield as subelement of datafield with default code 'a' and its text
                        subfield = ET.SubElement(datafield, 'subfield', code='a')
                        subfield.text = text.strip()
 
    # write tree to xml file
    ET.indent(tree, space='    ')
    xml_path = Path.home() / 'Downloads' / f'{Path(csv_path).stem}.xml'
    tree.write(xml_path, encoding='utf-8', xml_declaration=True)
    return xml_path
    # print(f'csv converted to xml at {xml_path}')
 
def select(radio: IntVar, string: StringVar) -> None:
    '''Select and convert files from one format to another'''
 
    if radio.get() == 0:
        # prompt user to select xml files to convert to csv
        xml_files = filedialog.askopenfiles(
            filetypes=[('XML file', '.xml')],
            title='Select XML files to convert to CSV'
        )
 
        # convert selected xml files to csv
        for xml_file in xml_files:
            csv_path = xml_to_csv(Path(xml_file.name))
            string.set(f'{string.get()}\nXML converted to CSV at {csv_path}')
    else:
        # prompt user to select csv files to convert to xml
        csv_files = filedialog.askopenfiles(
            filetypes=[('CSV file', '.csv')],
            title='Select CSV files to convert to XML'
        )
 
        # convert selected csv files to xml
        for csv_file in csv_files:
            xml_path = csv_to_xml(Path(csv_file.name))
            string.set(f'{string.get()}\nCSV converted to XML at {xml_path}')
 
def gui() -> None:
    '''Create GUI for end user'''
 
    # create window and apply style
    root = Tk()
    root.geometry('700x500')
    # root.resizable(False, False)
    root.title('S211 Converter')
 
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # running in a pyinstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # running in a normal python env
        base_path = Path(__file__).parent
   
    # set app icon
    icon_path = base_path / 'icon.ico'
    root.iconbitmap(default=icon_path)
 
    # create variable to track selection of radio buttons for conversion type
    radio = IntVar()
    ttk.Label(root, text='Select conversion type:').pack()
    ttk.Radiobutton(root, text='XML to CSV', variable=radio, value=0).pack()
    ttk.Radiobutton(root, text='CSV to XML', variable=radio, value=1).pack()
   
    # create variable to track output text
    string = StringVar()
 
    # create button to select files to convert based on selected conversion type
    ttk.Button(root, text='Select files', command=lambda: select(radio, string)).pack()
 
    # create label to display output text
    ttk.Label(root, textvariable=string).pack()
 
    # run the window
    root.mainloop()
 
if __name__ == '__main__':
    gui()