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
        # initialize defaultdict of record where each field is a list
        record_dict = defaultdict(list)
 
        # get and add leader to dict
        leader = record.find('.//xmlns:leader', namespaces)
        record_dict['Leader'].append(leader.text.strip())
 
        # iterate over each controlfield in the record
        for ctrl in record.findall('.//xmlns:controlfield', namespaces):
            # get controlfield tag number and text
            tag = ctrl.attrib['tag']
            text = (ctrl.text or '').strip()
 
            if tag == '005':
                # parse and format timestamp as iso
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

            if tag == '260':
                # get publication and distribution and use empty string if empty
                publication = (subfields[0].text or '').strip()
                distribution = (subfields[1].text or '').strip()

                # join publication and distribution separated by newline
                text = f'{publication}\n{distribution}'
            elif tag == '710' or tag == '110':
                # get corporate name and use empty string if empty
                text = corporate_name = (subfields[0].text or '').strip()

                # join corporate name and relator separated by newline
                if len(subfields) == 2:
                    relator = (subfields[1].text or '').strip()
                    text = f'{corporate_name}\n{relator}'
            elif tag == '856':
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
           
            # get field name based on tag number and add text to record's
            # respective field
            field_name = tag_dict[tag]
            record_dict[field_name].append(text)
       
        # add record to data list
        data.append(record_dict)
   
    # create dataframe with nested lists as strings separated by 2 newlines
    df = pd.DataFrame(data).fillna('').map(lambda x: '\n\n'.join(x))
 
    # write dataframe to csv file with signed utf-8 encoding to avoid any errors
    csv_path = Path.home() / 'Downloads' / f'{Path(xml_path).stem}.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f'XML converted to CSV at {csv_path}')
    return csv_path
 
def csv_to_xml(csv_path: Path | str) -> Path:
    '''Convert csv file to xml'''
 
    # detect encoding of csv file
    with open(csv_path, 'rb') as f:
        encoding = chardet.detect(f.read())['encoding']
 
    # convert csv dataframe with correct encoding and all values as strings
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
            # get field's cell and split string with 2+ newlines into list
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
                        # format iso timestamp as number
                        timestamp = datetime.fromisoformat(text)
                        text = timestamp.strftime('%Y%m%d%H%M%S.0')
 
                    # define controlfield with its appropriate tag number
                    ctrl = ET.SubElement(record, 'controlfield', tag=tag)
                    ctrl.text = text.strip()
                elif field_name == 'ID':
                    # only appears in delete file
                    ctrl = ET.SubElement(record, 'controlfield', tag='001')
                    ctrl.text = text.strip()
                else:
                    # skip to next iteration if field name is unknown
                    if field_name not in field_dict:
                        continue
                   
                    # define datafield with its appropriate tag number
                    tag = field_dict[field_name]
                    datafield = ET.SubElement(record, 'datafield', tag=tag)

                    if tag == '260':
                        # define publication (a) and distribution (b) subfields
                        sub_a = ET.SubElement(datafield, 'subfield', code='a')
                        sub_b = ET.SubElement(datafield, 'subfield', code='b')
 
                        # split text by newline and set text of subfield a
                        split_text = text.strip().split('\n')
                        sub_a.text = split_text[0].strip()
 
                        # set text of subfield b if it exists
                        if len(split_text) == 2:
                            sub_b.text = split_text[1].strip()
                    elif tag == '710' or tag == '110':
                        # define corporate name (a) and relator (e) subfields
                        sub_a = ET.SubElement(datafield, 'subfield', code='a')
                        sub_e = ET.SubElement(datafield, 'subfield', code='e')

                        # split text by newline and set text of subfield a
                        split_text = text.strip().split('\n')
                        sub_a.text = split_text[0].strip()

                        # set text of subfield e if it exists
                        if len(split_text) == 2:
                            sub_e.text = split_text[1].strip()
                    elif tag == '856':
                        # define link location (u) and display text (y) subfields
                        sub_u = ET.SubElement(datafield, 'subfield', code='u')
                        sub_y = ET.SubElement(datafield, 'subfield', code='y')
 
                        # parse url and query
                        url = urlparse(text)
                        query = parse_qs(url.query)
 
                        # get link location from url with query removed
                        link_location = url._replace(query='').geturl()
 
                        # get display text from query or set default value
                        if 'display_text' in query:
                            display_text = query['display_text'][0]
                        else:
                            display_text = 'Online access'
 
                        # set text of link location and display text subfields
                        sub_u.text = link_location.strip()
                        sub_y.text = display_text.strip()
                    else:
                        # define subfield a and set its text
                        sub_a = ET.SubElement(datafield, 'subfield', code='a')
                        sub_a.text = text.strip()
 
    # write tree to xml file
    ET.indent(tree, space='    ')
    xml_path = Path.home() / 'Downloads' / f'{Path(csv_path).stem}.xml'
    tree.write(xml_path, encoding='utf-8', xml_declaration=True)
    print(f'CSV converted to XML at {xml_path}')
    return xml_path
 
def select_files(bit: IntVar, text_box: Text) -> None:
    '''Select and convert files from one format to another'''

    # make text box editable
    text_box.config(state='normal')
 
    if bit.get() == 0:
        # prompt user to select xml files to convert to csv
        xml_files = filedialog.askopenfiles(
            filetypes=[('XML File', '.xml')],
            title='Select XML Files to Convert to CSV'
        )
 
        # convert selected xml files to csv and display output path in text box
        for xml_file in xml_files:
            csv_path = xml_to_csv(Path(xml_file.name))
            text_box.insert('end', f'XML Converted to CSV at {csv_path}\n')
    else:
        # prompt user to select csv files to convert to xml
        csv_files = filedialog.askopenfiles(
            filetypes=[('CSV File', '.csv')],
            title='Select CSV Files to Convert to XML'
        )
 
        # convert selected csv files to xml and display output path in text box
        for csv_file in csv_files:
            xml_path = csv_to_xml(Path(csv_file.name))
            text_box.insert('end', f'CSV Converted to XML at {xml_path}\n')
    
    # make text box uneditable
    text_box.config(state='disabled')
 
def gui() -> None:
    '''Create GUI for end user'''
 
    # create window and apply style
    root = Tk()
    root.geometry('650x400')
    root.minsize(350, 200)
    root.title('S211 Converter')

    # check if python script is running in a pyinstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
   
    # set app icon
    icon_path = base_path / 'icon.ico'
    root.iconbitmap(default=icon_path)

    # create radio buttons and variable to track conversion type selection
    radios = ttk.Frame(root)
    l = ttk.Label(radios, text='Select Conversion Type:')
    bit = IntVar()
    r1 = ttk.Radiobutton(radios, text='XML to CSV', variable=bit, value=0)
    r2 = ttk.Radiobutton(radios, text='CSV to XML', variable=bit, value=1)

    # pack widgets
    radios.pack(pady=5)
    l.pack(padx=5, side='left')
    r1.pack(padx=5, side='left')
    r2.pack(padx=5)
 
    # create buttons to select files to convert and to open downloads dir
    buttons = ttk.Frame(root)
    b1 = ttk.Button(buttons, text='Select Files to Convert',
                    command=lambda: select_files(bit, text_box))
    b2 = ttk.Button(buttons, text='Open Downloads Folder',
                    command=lambda: os.startfile(Path.home() / 'Downloads'))
    
    # create text box to display path of output file
    text_box = Text(root, font='TkDefaultFont', padx=5, pady=5, state='disabled')
    
    # pack widgets
    buttons.pack()
    b1.pack(side='left')
    b2.pack()
    text_box.pack(padx=15, pady=15, expand=True, fill='both')
 
    # run the window
    root.mainloop()
 
if __name__ == '__main__':
    gui()