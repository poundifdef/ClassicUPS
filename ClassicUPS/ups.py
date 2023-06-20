import base64
import json
import urllib
import xmltodict

from binascii import a2b_base64
from datetime import datetime
from dict2xml import dict2xml

EMPTY_VALUES = (None, '', [], (), {})


class UPSConnection(object):

    test_urls = {
        'rate': 'https://wwwcie.ups.com/ups.app/xml/Rate',
        'track': 'https://wwwcie.ups.com/ups.app/xml/Track',
        'ship_confirm': 'https://wwwcie.ups.com/ups.app/xml/ShipConfirm',
        'ship_accept': 'https://wwwcie.ups.com/ups.app/xml/ShipAccept',
    }
    production_urls = {
        'rate': 'https://onlinetools.ups.com/ups.app/xml/Rate',
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
        resp = urllib.urlopen(url, xml.encode('ascii', 'xmlcharrefreplace'))\
                .read()

        return UPSResult(resp)

    def tracking_info(self, *args, **kwargs):
        return TrackingInfo(self, *args, **kwargs)

    def create_shipment(self, *args, **kwargs):
        return Shipment(self, *args, **kwargs)

    def get_rates(self, *args, **kwargs):
        return Rate(self, *args, **kwargs)


class UPSResult(object):

    def __init__(self, response):
        self.response = response

    @property
    def xml_response(self):
        return self.response

    @property
    def dict_response(self):
        return json.loads(json.dumps(xmltodict.parse(self.xml_response)))


class Rate(object):
    SHIPPING_SERVICES = {
        '01': 'Next Day Air',
        '02': 'Second Day Air',
        '03': 'Ground',
        '07': 'Worlwide Express',
        '08': 'Worlwide Expedited',
        '11': 'Standard',
        '12': 'Three-Day Select',
        '13': 'Next Day Air Saver',
        '14': 'Next Day Air Early A.M.',
        '54': 'Worlwide Express Plus',
        '59': 'Second Day Air A.M.',
        '65': 'Saver',
        '82': 'Today Standard',
        '83': 'Today Dedicated Courrier',
        '84': 'Today Intercity',
        '85': 'Today Express',
        '86': 'Today Express Saver',
        'TDCB': 'Trade Direct Cross Border',
        'TDA': 'Trade Direct Air',
        'TDO': 'Trade Direct Ocean',
        '308': 'Freight LTL',
        '309': 'Freight LTL Guaranteed',
        '310': 'Freight LTL Urgent',
    }

    def __init__(self, ups_conn, from_addr, to_addr, dimensions, weight, description='',
                 dimensions_unit='IN', weight_unit='LBS'):
        rate_request = {
            'RatingServiceSelectionRequest': {
                'Request': {
                    'RequestAction': 'Rate',
                    'RequestOption': 'Shop',  # Rate returns the cost for a specific UPS service,
                    # Shop returns the costs for all available UPS services for the shipment
                },
                'Shipment': {
                    'Shipper': {
                        'ShipperNumber': ups_conn.shipper_number,
                        'Address': {
                            'CountryCode': from_addr['country'],
                            'PostalCode': from_addr['postal_code'],
                        },
                    },
                    'ShipTo': {
                        'Address': {
                            'CountryCode': to_addr['country'],
                            'PostalCode': to_addr['postal_code'],
                        },
                    },
                    'Package': {
                        'PackagingType': {
                            'Code': '02',  # Box (see http://www.ups.com/worldshiphelp/WS11/ENU/AppHelp/Codes/Package_Type_Codes.htm)
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
                    },
                    'ShipmentServiceOptions': {
                        'SaturdayPickupIndicator': True
                    }
                }
            },
        }

        if description not in EMPTY_VALUES:
            rate_request['RatingServiceSelectionRequest']['Shipment']['Description'] = description

        self.rate_result = ups_conn._transmit_request('rate', rate_request)

    @property
    def costs(self):
        result = []
        try:
            for rated_shipment in self.rate_result.dict_response['RatingServiceSelectionResponse']['RatedShipment']:
                service_code = rated_shipment['Service']['Code']
                result.append({
                    'service_code': service_code,
                    'service_title': self.SHIPPING_SERVICES.get(service_code, service_code),
                    'cost_transportation': rated_shipment['TransportationCharges']['MonetaryValue'],
                    'cost_other': rated_shipment['ServiceOptionsCharges']['MonetaryValue'],
                    'cost_total': rated_shipment['TotalCharges']['MonetaryValue'],
                    'currency': rated_shipment['TotalCharges']['CurrencyCode'],
                })
        except KeyError:
            return []

        return result


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

        # if error:
        #{
        #    u'Response': {
        #        u'ResponseStatusCode': u'0',
        #        u'TransactionReference': {
        #            u'CustomerContext': u'Get tracking status',
        #            u'XpciVersion': u'1.0'
        #        },
        #        u'ResponseStatusDescription': u'Failure',
        #        u'Error': {
        #            u'ErrorCode': u'151018',
        #            u'ErrorDescription':
        #            u'Invalid tracking number',
        #            u'ErrorSeverity': u'Hard'
        #        }
        #    }
        #}

    @property
    def shipment_activities(self):
        # Possible Status.StatusType.Code values:
        #   I: In Transit
        #   D: Delivered
        #   X: Exception
        #   P: Pickup
        #   M: Manifest

        try:
            shipment_activities = (self.result.dict_response['TrackResponse']
                                          ['Shipment']['Package']['Activity'])
            if type(shipment_activities) != list:
                shipment_activities = [shipment_activities]
            return shipment_activities
        except KeyError:
            return []

    @property
    def delivered(self):
        try:
            delivered = [x for x in self.shipment_activities
                         if x['Status']['StatusType']['Code'] == 'D']
            if delivered:
                return datetime.strptime(delivered[0]['Date'], '%Y%m%d')
        except KeyError:
            return {
                'error_code': self.result.dict_response['TrackResponse']['Response']['Error']['ErrorCode'],
                'error_message': self.result.dict_response['TrackResponse']['Response']['Error']['ErrorDescription']
            }

    @property
    def in_transit(self):
        try:
            in_transit = [x for x in self.shipment_activities
                         if x['Status']['StatusType']['Code'] == 'I']

            return len(in_transit) > 0
        except KeyError:
            return {
                'error_code': self.result.dict_response['TrackResponse']['Response']['Error']['ErrorCode'],
                'error_message': self.result.dict_response['TrackResponse']['Response']['Error']['ErrorDescription']
            }


class Shipment(object):
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

    DCIS_TYPES = {
        'no_signature': 1,
        'signature_required': 2,
        'adult_signature_required': 3,
        'usps_delivery_confiratmion': 4,
    }

    def __init__(self, ups_conn, from_addr, to_addr, dimensions, weight,
                 file_format='EPL', reference_numbers=None, shipping_service='ground', shipping_service_code=None,
                 description='', dimensions_unit='IN', weight_unit='LBS',
                 delivery_confirmation=None):

        if not shipping_service_code and shipping_service:
            shipping_service_code = self.SHIPPING_SERVICES[shipping_service]

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
                        'AttentionName': from_addr.get('attn') if from_addr.get('attn') else from_addr['name'],
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
                        'AttentionName': to_addr.get('attn') if to_addr.get('attn') else to_addr['name'],
                        'PhoneNumber': to_addr['phone'],
                        'Address': {
                            'AddressLine1': to_addr['address1'],
                            'City': to_addr['city'],
                            'StateProvinceCode': to_addr['state'],
                            'CountryCode': to_addr['country'],
                            'PostalCode': to_addr['postal_code'],
                            # 'ResidentialAddress': '',  # TODO: omit this if not residential
                        },
                    },
                    'Service': {  # TODO: add new service types
                        'Code': shipping_service_code,
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
                            'Code': '02',  # Box (see http://www.ups.com/worldshiphelp/WS11/ENU/AppHelp/Codes/Package_Type_Codes.htm)
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

        if delivery_confirmation:
            shipping_request['ShipmentConfirmRequest']['Shipment']['Package']['PackageServiceOptions']['DeliveryConfirmation'] = {
                'DCISType': self.DCIS_TYPES[delivery_confirmation]
            }

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
                shipping_request['ShipmentConfirmRequest']['Shipment']['ReferenceNumber'] = reference_dict

        if description not in EMPTY_VALUES:
            shipping_request['ShipmentConfirmRequest']['Shipment']['Description'] = description

        if from_addr.get('address2') not in EMPTY_VALUES:
            shipping_request['ShipmentConfirmRequest']['Shipment']['Shipper']['Address']['AddressLine2'] = from_addr['address2']

        if to_addr.get('company') not in EMPTY_VALUES:
            shipping_request['ShipmentConfirmRequest']['Shipment']['ShipTo']['CompanyName'] = to_addr['company']

        if to_addr.get('address2') not in EMPTY_VALUES:
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
    def currency(self):
        return self.confirm_result.dict_response['ShipmentConfirmResponse']['ShipmentCharges']['TotalCharges']['CurrencyCode']

    @property
    def tracking_number(self):
        tracking_number = self.confirm_result.dict_response['ShipmentConfirmResponse']['ShipmentIdentificationNumber']
        return tracking_number

    def get_label(self):
        raw_epl = self.accept_result.dict_response['ShipmentAcceptResponse']['ShipmentResults']['PackageResults']['LabelImage']['GraphicImage']
        return base64.b64encode(raw_epl)

    def save_label(self, fd):
        encoded_label = base64.b64decode(self.get_label())
        image_data = a2b_base64(encoded_label)
        fd.write(image_data)
