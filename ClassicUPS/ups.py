import json
import requests
import xmltodict

from binascii import a2b_base64
from datetime import datetime
from dict2xml import dict2xml

SHIPPING_SERVICES = {
    '1dayair': '01',  # Next Day Air
    '2dayair': '02',  # 2nd Day Air
    'ground': '03',  # Ground
    'express': '07',  # Express
    'worldwide_expedited': '08',  # Expedited
    'standard': '11',  # UPS Standard
    '3_day_select': '12',  # 3 Day Select
    'next_day_air_saver': '13',  # Next Day Air Saver
    'next_day_air_early_am': '14',  # Next Day Air Early AM
    'express_plus': '54',  # Express Plus
    '2nd_day_air_am': '59',  # 2nd Day Air A.M.
    'ups_saver': '65',  # UPS Saver.
    'ups_today_standard': '82',  # UPS Today Standard
    'ups_today_dedicated_courier': '83',  # UPS Today Dedicated Courier
    'ups_today_intercity': '84',  # UPS Today Intercity
    'ups_today_express': '85',  # UPS Today Express
    'ups_today_express_saver': '86',  # UPS Today Express Saver.
}

class UPSError(Exception):
    def __init__(self, message):
        self.message = message

class UPSConnection(object):

    test_urls = {
        'track': 'https://wwwcie.ups.com/ups.app/xml/Track',
        'ship_confirm': 'https://wwwcie.ups.com/ups.app/xml/ShipConfirm',
        'ship_accept': 'https://wwwcie.ups.com/ups.app/xml/ShipAccept',
        'rate': 'https://wwwcie.ups.com/ups.app/xml/Rate'
    }
    production_urls = {
        'track': 'https://onlinetools.ups.com/ups.app/xml/Track',
        'ship_confirm': 'https://onlinetools.ups.com/ups.app/xml/ShipConfirm',
        'ship_accept': 'https://onlinetools.ups.com/ups.app/xml/ShipAccept',
        'rate': 'https://onlinetools.ups.com/ups.app/xml/Rate'
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

        xml = u'''
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

        resp = requests.post(
            url,
            data=xml.replace('&', u'&#38;').encode('ascii', 'xmlcharrefreplace')
        )

        return UPSResult(resp.text)

    def tracking_info(self, *args, **kwargs):
        return TrackingInfo(self, *args, **kwargs)

    def create_shipment(self, *args, **kwargs):
        return Shipment(self, *args, **kwargs)

    def create_rates(self, *args, **kwargs):
        return Rates(self, *args, **kwargs)

    def check_shipping_valid(self, *args, **kwards):
        return ShippingValid(self, *args, **kwargs)

class UPSResult(object):

    def __init__(self, response):
        self.response = response

    @property
    def xml_response(self):
        return self.response

    @property
    def dict_response(self):
        return json.loads(json.dumps(xmltodict.parse(self.xml_response)))

class ShippingValid(object):
    def __init__(self, ups_conn, to_addr):
        self.result = ""

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
        # Possible Status.StatusType.Code values:
        #   I: In Transit
        #   D: Delivered
        #   X: Exception
        #   P: Pickup
        #   M: Manifest

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

    @property
    def in_transit(self):
        in_transit = [x for x in self.shipment_activities
                     if x['Status']['StatusType']['Code'] == 'I']

        return len(in_transit) > 0

class Rates(object):

    def __init__(self, ups_conn, from_addr, to_addr, packages,
                 dimensions_unit='IN', weight_unit='LBS'):

        packages_list = []
        for package in packages:
            dimensions = package['dimensions']
            weight = package['weight']
            packages_list.append({
                'PackagingType': {
                    'Code': package.get('packaging_type') or '02'
                },
                'Dimensions': {
                    'UnitOfMeasurement': {
                        'Code': dimensions_unit,
                        # default unit: inches (IN)
                    },
                    'Length': dimensions['length'],
                    'Width': dimensions['width'],
                    'Height': dimensions['height'],
                },
                'PackageWeight': {
                    'UnitOfMeasurement': {
                        'Code': weight_unit,
                        # default unit: pounds (LBS)
                    },
                    'Weight': weight,
                },
                'PackageServiceOptions': {},
            })

        rates_request = {"RatingServiceSelectionRequest": {
            "Request": {
                'TransactionReference': {
                    'CustomerContext': 'rate request',
                    'XpciVersion': '1.0001',
                },
                'RequestAction': 'Shop',
                'RequestOption': 'Shop',
            },
            "Shipment": {
                "Shipper": {
                    "ShipperNumber": ups_conn.shipper_number,
                    "Address": {
                        "PostalCode": from_addr["postal_code"],
                        "CountryCode": from_addr["country"]
                    }
                },
                "ShipTo": {
                    "Address": {
                        "PostalCode": to_addr["postal_code"],
                        "CountryCode": to_addr["country"],
                    }
                },
                "ShipFrom": {
                    "Address": {
                        "PostalCode": from_addr["postal_code"],
                        "City": from_addr["city"],
                        "CountryCode": from_addr["country"]
                    }
                },
                "Package": packages_list,
                "RateInformation": {
                    "NegotiatedRatesIndicator": ""
                }
            }
        }}

        if from_addr.get('state'):
            shipping_request['RatingServiceSelectionRequest']['Shipment']['Shipper']['Address']['StateProvinceCode'] = from_addr['state']
            shipping_request['RatingServiceSelectionRequest']['Shipment']['ShipFrom']['Address']['StateProvinceCode'] = from_addr['state']

        if to_addr.get('state'):
            shipping_request['RatingServiceSelectionRequest']['Shipment']['ShipTo']['Address']['StateProvinceCode'] = to_addr['state']

        self.rate_result = ups_conn._transmit_request('rate', rates_request)

        if self.rate_result.dict_response['RatingServiceSelectionResponse'][
                'Response']['ResponseStatusCode'] == '0':
            error_string = self.rate_result.dict_response[
                'RatingServiceSelectionResponse']['Response']['Error'][
                'ErrorDescription']
            raise UPSError(error_string)


class Shipment(object):

    DCIS_TYPES = {
        'no_signature': 1,
        'signature_required': 2,
        'adult_signature_required': 3,
        'usps_delivery_confiratmion': 4,
    }

    def __init__(self, ups_conn, from_addr, to_addr, packages, shipping_service, reference_numbers=None,
                 file_format='EPL',
                 description='', dimensions_unit='IN', weight_unit='LBS',
                 delivery_confirmation=None, ItemizedPaymentInformation=None):

        self.file_format = file_format

        packages_list = []
        for package in packages:
            dimensions = package['dimensions']
            weight = package['weight']
            packages_list.append({
                'PackagingType': {
                    'Code': package.get('packaging_type') or '02'
                },
                'Dimensions': {
                    'UnitOfMeasurement': {
                        'Code': dimensions_unit,
                        # default unit: inches (IN)
                    },
                    'Length': dimensions['length'],
                    'Width': dimensions['width'],
                    'Height': dimensions['height'],
                },
                'PackageWeight': {
                    'UnitOfMeasurement': {
                        'Code': weight_unit,
                        # default unit: pounds (LBS)
                    },
                    'Weight': weight,
                },
                'PackageServiceOptions': {},
            })

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
                        'AttentionName': from_addr.get('attn') if from_addr.get('attn') else from_addr['name'],
                        'PhoneNumber': from_addr['phone'],
                        'ShipperNumber': ups_conn.shipper_number,
                        'Address': {
                            'AddressLine1': from_addr['address1'],
                            'City': from_addr['city'],
                            'CountryCode': from_addr['country'],
                            'PostalCode': from_addr['postal_code'],
                        },
                    },
                    'ShipTo' : {
                        'CompanyName': to_addr['name'],
                        'AttentionName': to_addr.get('attn') if to_addr.get('attn') else to_addr['name'],
                        'PhoneNumber': to_addr['phone'],
                        'Address': {
                            'AddressLine1': to_addr['address1'],
                            'City': to_addr['city'],
                            'CountryCode': to_addr['country'],
                            'PostalCode': to_addr['postal_code'],
                            # 'ResidentialAddress': '',  # TODO: omit this if not residential
                        },
                    },
                    'Package': packages_list,
                    'Service' : {  # TODO: add new service types
                        'Code': SHIPPING_SERVICES[shipping_service],
                        'Description': shipping_service,
                    },
                    'PaymentInformation': {  # TODO: Other payment information
                        'Prepaid': {
                            'BillShipper': {
                                'AccountNumber': ups_conn.shipper_number,
                            },
                        },
                    },
                    'ShipmentServiceOptions': {},
                    'ItemizedPaymentInformation': {},
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

        if to_addr.get('email'):
            notifications_codes = ['6','8','7']
            notificationsShipment = []
            for notification_code in notifications_codes:
                notificationsShipment.append({
                    'NotificationCode': int(notification_code),
                    'EMailMessage': {
                        'EMailAddress': to_addr['email']
                    },
                    'Locale': {
                        'Language': 'SPA',
                        'Dialect': 97,
                    }
                })
            shipping_request['ShipmentConfirmRequest']['Shipment']['ShipmentServiceOptions']['Notification'] = notificationsShipment
            # shipping_request['ShipmentConfirmRequest']['Shipment']['ShipmentServiceOptions'] = {
            #     'Notification': {
            #         'NotificationCode': 6,
            #         'EMailMessage': {
            #             'EMailAddress': to_addr['email']
            #         },
            #         'Locale': {
            #             'Language': 'SPA',
            #             'Dialect': 97,
            #         }
            #     },
            #     'Notification': {
            #         'NotificationCode': 8,
            #         'EMailMessage': {
            #             'EMailAddress': to_addr['email']
            #         },
            #         'Locale': {
            #             'Language': 'SPA',
            #             'Dialect': 97,
            #         }
            #     },
            #     'Notification': {
            #         'NotificationCode': 7,
            #         'EMailMessage': {
            #             'EMailAddress': to_addr['email']
            #         },
            #         'Locale': {
            #             'Language': 'SPA',
            #             'Dialect': 97,
            #         }
            #     },
            # }
        if delivery_confirmation:
            shipping_request['ShipmentConfirmRequest']['Shipment']['Package']['PackageServiceOptions']['DeliveryConfirmation'] = {
                'DCISType': self.DCIS_TYPES[delivery_confirmation]
            }
        if ItemizedPaymentInformation == "02":
            types = ['01',ItemizedPaymentInformation]
            ShipmentCharge = []
            for type_ups in types:
                ShipmentCharge.append({
                                'Type': type_ups,
                                'BillShipper': {
                                    'AccountNumber':  ups_conn.shipper_number,
                                },
                        })
            shipping_request['ShipmentConfirmRequest']['Shipment']['ItemizedPaymentInformation']['ShipmentCharge'] = ShipmentCharge
        elif ItemizedPaymentInformation != "02":
            shipping_request['ShipmentConfirmRequest']['Shipment']['ItemizedPaymentInformation'] = {
                'ShipmentCharge': {
                    'Type': ItemizedPaymentInformation,
                    'BillShipper': {
                        'AccountNumber':  ups_conn.shipper_number
                    },
                },
            }
        if ItemizedPaymentInformation:
            del shipping_request['ShipmentConfirmRequest']['Shipment']['PaymentInformation']
        else:
            del shipping_request['ShipmentConfirmRequest']['Shipment']['ItemizedPaymentInformation']
        if reference_numbers:
            reference_dict = []
            for ref_code, ref_number in enumerate(reference_numbers):
                # allow custom reference codes to be set by passing tuples.
                # according to the docs ("Shipping Package -- WebServices
                # 8/24/2013") ReferenceNumber/Code should hint on the type of
                # the reference number. a list of codes can be found in
                # appendix I (page 503) in the same document.
                try:
                    ref_code, ref_number = ref_number
                except:
                    pass

                reference_dict.append({
                    'Code': ref_code,
                    'Value': ref_number
                })
            #reference_dict[0]['BarCodeIndicator'] = '1'

            if from_addr['country'] == 'US' and to_addr['country'] == 'US':
                shipping_request['ShipmentConfirmRequest']['Shipment']['Package']['ReferenceNumber'] = reference_dict
            else:
                shipping_request['ShipmentConfirmRequest']['Shipment']['Description'] = description
                shipping_request['ShipmentConfirmRequest']['Shipment']['ReferenceNumber'] = reference_dict
        shipping_request['ShipmentConfirmRequest']['Shipment']['Description'] = description or ''

        if from_addr.get('address2'):
            shipping_request['ShipmentConfirmRequest']['Shipment']['Shipper']['Address']['AddressLine2'] = from_addr['address2']

        if from_addr.get('state'):
            shipping_request['ShipmentConfirmRequest']['Shipment']['Shipper']['Address']['StateProvinceCode'] = from_addr['state']

        if to_addr.get('company'):
            shipping_request['ShipmentConfirmRequest']['Shipment']['ShipTo']['CompanyName'] = to_addr['company']

        if to_addr.get('address2'):
            shipping_request['ShipmentConfirmRequest']['Shipment']['ShipTo']['Address']['AddressLine2'] = to_addr['address2']

        if to_addr.get('state'):
            shipping_request['ShipmentConfirmRequest']['Shipment']['ShipTo']['Address']['StateProvinceCode'] = to_addr['state']

        self.confirm_result = ups_conn._transmit_request('ship_confirm', shipping_request)

        if 'ShipmentDigest' not in self.confirm_result.dict_response['ShipmentConfirmResponse']:
            error_string = self.confirm_result.dict_response['ShipmentConfirmResponse']['Response']['Error']['ErrorDescription']
            raise UPSError(error_string)

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

    def get_label(self):
        package_results = self.accept_result.dict_response['ShipmentAcceptResponse']['ShipmentResults']['PackageResults']
        label_list = []
        if isinstance(package_results, dict):
            raw_epl = package_results['LabelImage']['GraphicImage']
            label_list.append(a2b_base64(raw_epl))
        elif isinstance(package_results, list):
            for label in package_results:
                raw_epl = label['LabelImage']['GraphicImage']
                label_list.append(a2b_base64(raw_epl))
        return label_list

    def save_label(self, fd):
        fd.write(self.get_label()[0])
