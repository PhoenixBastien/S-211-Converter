import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import IntVar, Text, Tk, filedialog, ttk
from urllib.parse import urlparse, urlencode, parse_qs
 
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
 
def xml_to_csv(xml_path: Path | str) -> Path:
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
                # get publication and distribution and use empty string if empty
                publication = (subfields[0].text or '').strip()
                distribution = (subfields[1].text or '').strip()

                # join publication and distribution separated by newline
                text = f'{publication}\n{distribution}'
            elif tag == '710' or tag == '110': # Corporate Name or Main Entry Corporate Name
                # get corporate name and use empty string if empty
                corporate_name = (subfields[0].text or '').strip()
                text = corporate_name

                # join corporate name and relator separated by newline if latter exists
                if len(subfields) == 2:
                    relator = (subfields[1].text or '').strip()
                    text = f'{corporate_name}\n{relator}'
            elif tag == '856': # URL
                # get link location and display text
                link_location = subfields[0].text.strip()
                display_text = subfields[1].text.strip()

                # join link location and display text in a url
                url = urlparse(link_location)
                query = urlencode({'display_text': display_text})
                text = url._replace(query=query).geturl()
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
    csv_path = Path.home() / 'Downloads' / Path(xml_path).with_suffix('.csv')
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f'XML converted to CSV at {csv_path.as_posix()}')
    return csv_path
 
def csv_to_xml(csv_path: Path | str) -> Path:
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

                if field_name.lower() == 'leader':
                    # define leader as subelement of record and set its text
                    leader = ET.SubElement(record, 'leader')
                    leader.text = text.strip()
                elif field_name.startswith('controlfield'):
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
                        # define publication and distribution as subfields of datafield with codes 'a' and 'b' respectively
                        subfield_a = ET.SubElement(datafield, 'subfield', code='a')
                        subfield_b = ET.SubElement(datafield, 'subfield', code='b')
 
                        # split text by newline and set text of publication subfield
                        split_text = text.strip().split('\n')
                        subfield_a.text = split_text[0].strip()
 
                        # set text of distribution subfield if it exists
                        if len(split_text) == 2:
                            subfield_b.text = split_text[1].strip()
                    elif tag == '710' or tag == '110': # Corporate Name or Main Entry Corporate Name
                        # define corporate name and relator as subfields of datafield with codes 'a' and 'e' respectively
                        subfield_a = ET.SubElement(datafield, 'subfield', code='a')
                        subfield_e = ET.SubElement(datafield, 'subfield', code='e')

                        # split text by newline and set text of corporate name subfield
                        split_text = text.strip().split('\n')
                        subfield_a.text = split_text[0].strip()

                        # set text of second subfield if it exists
                        if len(split_text) == 2:
                            subfield_e.text = split_text[1].strip()
                    elif tag == '856': # URL
                        # define link location and display text as subfields of datafield with with codes 'u' and 'y' respectively
                        subfield_u = ET.SubElement(datafield, 'subfield', code='u')
                        subfield_y = ET.SubElement(datafield, 'subfield', code='y')
 
                        # parse url and query
                        url = urlparse(text)
                        query = parse_qs(url.query)
 
                        # get link location from parsed url with query removed
                        link_location = url._replace(query='').geturl()
 
                        # get display text from parsed query if it exists or default to 'Online access'
                        display_text = query['display_text'][0] \
                            if 'display_text' in query else 'Online access'
 
                        # set text of link location and display text subfields
                        subfield_u.text = link_location.strip()
                        subfield_y.text = display_text.strip()
                    else:
                        # define subfield of datafield with default code 'a' and set its text
                        subfield_a = ET.SubElement(datafield, 'subfield', code='a')
                        subfield_a.text = text.strip()
 
    # write tree to xml file
    ET.indent(tree, space='    ')
    xml_path = Path.home() / 'Downloads' / Path(csv_path).with_suffix('.xml')
    tree.write(xml_path, encoding='utf-8', xml_declaration=True)
    print(f'CSV converted to XML at {xml_path.as_posix()}')
    return xml_path
 
def select(radio: IntVar, text: Text) -> None:
    '''Select and convert files from one format to another'''

    text.config(state='normal')
 
    if radio.get() == 0:
        # prompt user to select xml files to convert to csv
        xml_files = filedialog.askopenfiles(
            filetypes=[('XML file', '.xml')],
            title='Select XML files to convert to CSV'
        )
 
        # convert selected xml files to csv and display output path in text box
        for xml_file in xml_files:
            csv_path = xml_to_csv(Path(xml_file.name))
            text.insert('end', f'XML converted to CSV at {csv_path.as_posix()}\n')
    else:
        # prompt user to select csv files to convert to xml
        csv_files = filedialog.askopenfiles(
            filetypes=[('CSV file', '.csv')],
            title='Select CSV files to convert to XML'
        )
 
        # convert selected csv files to xml and display output path in text box
        for csv_file in csv_files:
            xml_path = csv_to_xml(Path(csv_file.name))
            text.insert('end', f'CSV converted to XML at {xml_path.as_posix()}\n')
    
    text.config(state='disabled')
 
def gui() -> None:
    '''Create GUI for end user'''
 
    # create window and apply style
    root = Tk()
    root.geometry('650x400')
    root.resizable(width=False, height=False)
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
    radios = ttk.Frame(root)
    radios.pack(pady=5)
    ttk.Label(radios, text='Select conversion type:').pack(padx=5, side='left')
    ttk.Radiobutton(radios, text='XML to CSV',
                    variable=radio, value=0).pack(padx=5, side='left')
    ttk.Radiobutton(radios, text='CSV to XML',
                    variable=radio, value=1).pack(padx=5)

    text = Text(root, font='TkDefaultFont', width=100, height=20,
                   padx=5, pady=5, state='disabled')
 
    # create button to select files to convert based on selected conversion type
    buttons = ttk.Frame(root)
    buttons.pack()
    ttk.Button(buttons, text='Select files to convert',
               command=lambda: select(radio, text)).pack(side='left')
    ttk.Button(buttons, text='Open downloads folder',
               command=lambda: os.startfile(Path.home() / 'Downloads')).pack()
    
    # create text box to display output text
    text.pack(padx=15, pady=15)
 
    # run the window
    root.mainloop()
 
if __name__ == '__main__':
    gui()