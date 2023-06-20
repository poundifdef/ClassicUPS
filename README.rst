Update, 9/2022: Looking for a maintainer! If you're interested, please send me an email.

ClassicUPS: A Useful UPS Library
================================

ClassicUPS is an Apache2 Licensed wrapper around the UPS API for creating
shipping labels and fetching a package's tracking status. This library by no
means encompasses all of the UPS functionality, but it is suitable for some of
the most common shipping-related common tasks.


Features
--------

- Track delivery status of tracking number

- Create prepaid shipping labels in GIF or EPL (thermal printer) format


Installation
------------

Installation is easy:

.. code-block:: bash

    $ pip install ClassicUPS

ClassicUPS depends on libxml2 and libxslt. On Ubuntu, the packages are
``libxml2-dev`` and ``libxslt-dev``.

Quickstart
----------

Create a UPSConnection object, which gives you access to common UPS methods:

.. code-block:: python

    from ClassicUPS import UPSConnection

    # Credentials obtained from the UPS website
    ups = UPSConnection(license_number,
                        user_id,
                        password,
                        shipper_number,  # Optional if you are not creating a shipment
                        debug=True)      # Use the UPS sandbox API rather than prod


To get rates comparison for all available UPS services for given addresses and package properties:

.. code-block:: python

    from_addr = {
        'name': 'Google',
        'address1': '1600 Amphitheatre Parkway',
        'city': 'Mountain View',
        'state': 'CA',
        'country': 'US',
        'postal_code': '94043',
        'phone': '6502530000'
    }
    to_addr = {
        'name': 'President',
        'address1': '1600 Pennsylvania Ave',
        'city': 'Washington',
        'state': 'DC',
        'country': 'US',
        'postal_code': '20500',
        'phone': '2024561111'
    }
    dimensions = {  # in inches (by default)
        'length': 1,
        'width': 4,
        'height': 9
    }
    weight = 10  # in lbs (by default)

    # Get rates. It returns array of all available services and cost details.
    # You can use cost.service_code as a shipping_service_code parameter of create_shipment method.
    rates = ups.get_rates(from_addr, to_addr, dimensions, weight)

    # Example output of rates.costs:
    #[
    #    {
    #        'service_code': u'03',
    #        'service_title': 'Ground',
    #        'cost_transportation': u'14.69',
    #        'cost_other': u'0.00',
    #        'cost_total': u'14.69',
    #        'currency': u'USD'
    #    },
    #    {
    #
    #        'service_code': u'12',
    #        'service_title': 'Three-Day Select',
    #        'cost_transportation': u'52.35',
    #        'cost_other': u'0.00',
    #        'cost_total': u'52.35',
    #        'currency': u'USD'
    #    }
    #]

    for cost in rates.costs:
        print cost['service_code']
        print cost['service_title']
        print cost['cost_total']
        print cost['currency']


Create shipment and save shipping label as GIF file:

.. code-block:: python

    # Create the shipment. Use file_format='EPL' for a thermal-printer-compatible EPL
    shipment = ups.create_shipment(from_addr, to_addr, dimensions, weight,
                                   file_format='GIF')

    # Print information about our shipment
    print shipment.cost
    print shipment.tracking_number

    # Save the shipping label to print, email, etc
    shipment.save_label(open('label.gif', 'wb'))


Check the delivery date of a package.

.. code-block:: python

    tracking = ups.tracking_info('1Z12345E0291980793')
    print tracking.in_transit
    print tracking.delivered
