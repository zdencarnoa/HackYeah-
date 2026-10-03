import pytest

from app.detection.domains import domain_of, registrable


@pytest.mark.parametrize(("host", "expected"), [
    ("lakeside-logistics.example", "lakeside-logistics.example"),
    ("login.lakeside-logistics.example", "lakeside-logistics.example"),
    ("Login.Micr0soft-Example.test.", "micr0soft-example.test"),
    ("accountprotection.microsoft.example", "microsoft.example"),
    ("shop.example.co.uk", "example.co.uk"),
    ("www.bank.com.pl", "bank.com.pl"),
    ("com.pl", "com.pl"),
    ("192.0.2.10", "192.0.2.10"),
    ("localhost", "localhost"),
    ("", ""),
])
def test_registrable(host, expected):
    assert registrable(host) == expected


@pytest.mark.parametrize(("address", "expected"), [
    ("security@Micr0soft-Example.test", "micr0soft-example.test"),
    ("no-domain", ""),
    ("", ""),
])
def test_domain_of(address, expected):
    assert domain_of(address) == expected
