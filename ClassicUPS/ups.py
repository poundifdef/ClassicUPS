import requests
from dict2xml import dict2xml
import xmltodict
import json
import os
import tempfile
import shutil
import urllib

from binascii import a2b_base64
from datetime import datetime


class UPSConnection(object):

    test_urls = {
        'track': 'https://wwwcie.ups.com/ups.app/xml/Track',
        'ship_confirm': 'https://wwwcie.ups.com/ups.app/xml/ShipConfirm',
        'ship_accept': 'https://wwwcie.ups.com/ups.app/xml/ShipAccept',
    }
    production_urls = {
        'track': 'https://onlinetools.ups.com/ups.app/xml/Track',
        'ship_confirm': 'https://onlinetools.ups.com/ups.app/xml/ShipConfirm',
        'ship_accept': 'https://onlinetools.ups.com/ups.app/xml/ShipAccept',
    }

    def __init__(self, license_number, user_id, password, shipper_number=None,
                 debug=False):

        self.license_number = license_number
        self.user_id = user_id
        self.password = password
        self.shipper_number = shipper_number
        self.debug = debug

    def _generate_xml(self, url_action, ups_request):
        access_request = {
            'AccessRequest': {
                'AccessLicenseNumber': self.license_number,
                'UserId': self.user_id,
                'Password': self.password,
            }
        }

        xml = '''
        <?xml version="1.0"?>
        {access_request_xml}

        <?xml version="1.0"?>
        {api_xml}
        '''.format(
            request_type=url_action,
            access_request_xml=dict2xml(access_request),
            api_xml=dict2xml(ups_request),
        )

        return xml

    def _transmit_request(self, url_action, ups_request):
        url = self.production_urls[url_action]
        if self.debug:
            url = self.test_urls[url_action]

        xml = self._generate_xml(url_action, ups_request)
        resp = requests.post(url, data=xml)

        return UPSResult(resp)

    def tracking_info(self, *args, **kwargs):
        return TrackingInfo(self, *args, **kwargs)

    def create_shipment(self, *args, **kwargs):
        return Shipment(self, *args, **kwargs)

class UPSResult(object):

    def __init__(self, response):
        self.response = response

    @property
    def xml_response(self):
        return self.response.text

    @property
    def dict_response(self):
        return json.loads(json.dumps(xmltodict.parse(self.xml_response)))

class TrackingInfo(object):

    def __init__(self, ups_conn, tracking_number):
        self.tracking_number = tracking_number

        tracking_request = {
            'TrackRequest': {
                'Request': {
                    'TransactionReference': {
                        'CustomerContext': 'Get tracking status',
                        'XpciVersion': '1.0',
                    },
                    'RequestAction': 'Track',
                    'RequestOption': 'activity',
                },
                'TrackingNumber': tracking_number,
            },
        }

        self.result = ups_conn._transmit_request('track', tracking_request)

    @property
    def shipment_activities(self):
        shipment_activities = (self.result.dict_response['TrackResponse']
                                      ['Shipment']['Package']['Activity'])
        if type(shipment_activities) != list:
            shipment_activities = [shipment_activities]

        return shipment_activities

    @property
    def delivered(self):
        delivered = [x for x in self.shipment_activities
                     if x['Status']['StatusType']['Code'] == 'D']
        if delivered:
            return datetime.strptime(delivered[0]['Date'], '%Y%m%d')

class Shipment(object):
    SHIPPING_SERVICES = {
        '1dayair': '01',
        '2dayair': '02',
        'ground': '03',
        'worldwide_expedited': '08',
    }

    def __init__(self, ups_conn, from_addr, to_addr, dimensions, weight,
                 file_format='EPL', reference_numbers=None, shipping_service='ground'):

        self.file_format = file_format
        shipping_request = {
            'ShipmentConfirmRequest': {
                'Request': {
                    'TransactionReference': {
                        'CustomerContext': 'get new shipment',
                        'XpciVersion': '1.0001',
                    },
                    'RequestAction': 'ShipConfirm',
                    'RequestOption': 'nonvalidate',  # TODO: what does this mean?
                },
                'Shipment': {
                    'Shipper': {
                        'Name': from_addr['name'],
                        'PhoneNumber': from_addr['phone'],
                        'ShipperNumber': ups_conn.shipper_number,
                        'Address': {
                            'AddressLine1': from_addr['address1'],
                            'City': from_addr['city'],
                            'StateProvinceCode': from_addr['state'],
                            'CountryCode': from_addr['country'],
                            'PostalCode': from_addr['postal_code'],
                        },
                    },
                    'ShipTo' : {
                        'CompanyName': to_addr['name'],
                        'AttentionName': to_addr['name'],
                        'PhoneNumber': to_addr['phone'],
                        'Address': {
                            'AddressLine1': to_addr['address1'],
                            'City': to_addr['city'],
                            'StateProvinceCode': to_addr['state'],
                            'CountryCode': to_addr['country'],
                            'PostalCode': to_addr['postal_code'],
                            'ResidentialAddress': '',  # TODO: omit this if not residential
                        },
                    },
                    'Service' : {  # TODO: add new service types
                        'Code': self.SHIPPING_SERVICES[shipping_service],
                        'Description': shipping_service,
                    },
                    'PaymentInformation': {  # TODO: Other payment information
                        'Prepaid': {
                            'BillShipper': {
                                'AccountNumber': ups_conn.shipper_number,
                            },
                        },
                    },
                    'Package': {
                        'PackagingType': {
                            'Code': '02',
                        },
                        'Dimensions': {
                            'UnitOfMeasurement': {
                                'Code': 'IN',
                            },
                            'Length': dimensions['length'],
                            'Width': dimensions['width'],
                            'Height': dimensions['height'],
                        },
                        'PackageWeight': {
                            'Weight': weight,  # Units are pounds (lbs)
                        },
                        'PackageServiceOptions': '',  # TODO: insured value, verbal confirmation, etc
                    },
                },
                'LabelSpecification': {  # TODO: support GIF and EPL (and others)
                    'LabelPrintMethod': {
                        'Code': file_format,
                    },
                    'LabelStockSize': {
                        'Width': '6',
                        'Height': '4',
                    },
                    'HTTPUserAgent': 'Mozilla/4.5',
                    'LabelImageFormat': {
                        'Code': 'GIF',
                    },
                },
            },
        }

        if reference_numbers:
            reference_dict = []
            for ref_code, ref_number in enumerate(reference_numbers):
                reference_dict.append({
                    'Code': ref_code,
                    'Value': ref_number
                })
            #reference_dict[0]['BarCodeIndicator'] = '1'

            shipping_request['ShipmentConfirmRequest']['Shipment']['Package']['ReferenceNumber'] = reference_dict

        if from_addr.get('address2'):
            shipping_request['ShipmentConfirmRequest']['Shipment']['Shipper']['Address']['AddressLine2'] = from_addr['address2']

        if to_addr.get('company'):
            shipping_request['ShipmentConfirmRequest']['Shipment']['ShipTo']['CompanyName'] = to_addr['company']

        if to_addr.get('address2'):
            shipping_request['ShipmentConfirmRequest']['Shipment']['ShipTo']['Address']['AddressLine2'] = to_addr['address2']

        self.confirm_result = ups_conn._transmit_request('ship_confirm', shipping_request)

        if 'ShipmentDigest' not in self.confirm_result.dict_response['ShipmentConfirmResponse']:
            error_string = self.confirm_result.dict_response['ShipmentConfirmResponse']['Response']['Error']['ErrorDescription']
            raise Exception(error_string)

        confirm_result_digest = self.confirm_result.dict_response['ShipmentConfirmResponse']['ShipmentDigest']
        ship_accept_request = {
            'ShipmentAcceptRequest': {
                'Request': {
                    'TransactionReference': {
                        'CustomerContext': 'shipment accept reference',
                        'XpciVersion': '1.0001',
                    },
                    'RequestAction': 'ShipAccept',
                },
                'ShipmentDigest': confirm_result_digest,
            }
        }

        self.accept_result = ups_conn._transmit_request('ship_accept', ship_accept_request)

    @property
    def cost(self):
        total_cost = self.confirm_result.dict_response['ShipmentConfirmResponse']['ShipmentCharges']['TotalCharges']['MonetaryValue']
        return float(total_cost)

    @property
    def tracking_number(self):
        tracking_number = self.confirm_result.dict_response['ShipmentConfirmResponse']['ShipmentIdentificationNumber']
        return tracking_number

    def save_label(self, fd):
        raw_epl = self.accept_result.dict_response['ShipmentAcceptResponse']['ShipmentResults']['PackageResults']['LabelImage']['GraphicImage']
        binary = a2b_base64(raw_epl)
        fd.write(binary)
