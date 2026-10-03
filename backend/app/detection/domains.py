"""Domain helpers shared by the checks. Task 4 adds homoglyphs and lookalikes here.

Offline on purpose: no public-suffix download, no DNS.
"""

import ipaddress

MULTI_PART_SUFFIXES = {"co.uk", "org.uk", "com.au", "com.pl", "org.pl", "net.pl",
                       "gov.pl", "edu.pl", "waw.pl"}


def registrable(host: str) -> str:
    """The part of a host name that is actually bought:
    login.lakeside-logistics.example -> lakeside-logistics.example.
    IP addresses are returned unchanged."""
    host = host.strip().lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def domain_of(address: str) -> str:
    """The lowercased domain of an email address; "" when it has none."""
    return address.rpartition("@")[2].strip().lower() if "@" in address else ""
