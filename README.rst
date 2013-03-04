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

Quickstart
----------

Create a UPSConnection object, which gives you access to common UPS methods:

.. code-block:: python

    from ClassicUPS.ups import UPSConnection

    # Credentials obtained from the UPS website
    ups = UPSConnection(license_number,
                        user_id,
                        password,
                        shipper_number,  # Optional if you are not creating a shipment
                        debug=True)      # Use the UPS sandbox API rather than prod

Check the delivery date of a package.

.. code-block:: python

    print ups.tracking_info('1Z12345E0291980793').delivered

Create shipment and save shipping label as GIF file:

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
    dimensions = {  # in inches
        'length': 1,
        'width': 4,
        'height': 9
    }
    weight = 10  # in lbs

    # Create the shipment. Use file_format='EPL' for a thermal-printer-compatible EPL
    shipment = ups.create_shipment(from_addr, to_addr, dimensions, weight, file_format='GIF')

    # Print information about our shipment
    print shipment.cost
    print shipment.tracking_number

    # Save the shipping label to print, email, etc
    shipment.save_label(open('label.gif', 'wb'))
