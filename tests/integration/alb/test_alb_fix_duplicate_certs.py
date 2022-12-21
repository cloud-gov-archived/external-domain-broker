import pytest  # noqa F401

from tests.lib.factories import (
    CertificateFactory,
    ALBServiceInstanceFactory,
)

from broker.check_duplicate_certs import get_duplicate_certs_for_service, fix_duplicate_alb_certs, get_matching_alb_listener_arns_for_cert_arns

def test_get_duplicate_certs_for_service(no_context_clean_db, no_context_app):
  with no_context_app.app_context():
    service_instance = ALBServiceInstanceFactory.create(id="1234")
    certificate1 = CertificateFactory.create(
        service_instance=service_instance,
    )
    certificate2 = CertificateFactory.create(
        service_instance=service_instance,
    )
    certificate3 = CertificateFactory.create(
        service_instance=service_instance,
    )
    service_instance.current_certificate_id = certificate1.id

    no_context_clean_db.session.commit()

    results = get_duplicate_certs_for_service(service_instance.id)

    assert len(results) == 2
    assert results == [certificate2, certificate3]

def test_fix_duplicate_certs_for_service(no_context_clean_db, no_context_app):
  with no_context_app.app_context():
    service_instance = ALBServiceInstanceFactory.create(id="1234")
    certificate1 = CertificateFactory.create(
        service_instance=service_instance,
    )
    CertificateFactory.create(
        service_instance=service_instance,
    )
    CertificateFactory.create(
        service_instance=service_instance,
    )
    service_instance.current_certificate_id = certificate1.id

    no_context_clean_db.session.commit()

    results = get_duplicate_certs_for_service(service_instance.id)
    assert len(results) == 2
    
    fix_duplicate_alb_certs()
    no_context_clean_db.session.commit()
    
    results = get_duplicate_certs_for_service(service_instance.id)
    assert len(results) == 0

def test_get_matching_alb_listener_arns_for_single_cert_arn(alb):
    alb.expect_get_certificates_for_listener("listener-arn-0", 1)
    results = get_matching_alb_listener_arns_for_cert_arns(["listener-arn-0/certificate-arn"])
    assert results == {
      "listener-arn-0/certificate-arn": "listener-arn-0"
    }

def test_get_matching_alb_listener_arns_breaks_correctly(alb):
    class FakeALBTest:
      def __init__(self):
        self.requested_listener_arns = []

      def describe_listener_certificates(self, ListenerArn=""):
        self.requested_listener_arns.append(ListenerArn)
        return {
          "Certificates": [{
            "CertificateArn": "listener-arn-0/certificate-arn"
          }],
        }
    
    fakeAlbTester = FakeALBTest()
    get_matching_alb_listener_arns_for_cert_arns(
      ["listener-arn-0/certificate-arn"],
      listener_arns=["listener-arn-0", "listener-arn-1"],
      alb=fakeAlbTester
    )
    # Only request for the first listener was made because it
    # contained all of the specified certificate ARNs
    assert fakeAlbTester.requested_listener_arns == [
      "listener-arn-0"
    ]

def test_get_matching_alb_listener_arns_for_multiple_cert_arns(alb):
    alb.expect_get_certificates_for_listener("listener-arn-0", 1)
    results = get_matching_alb_listener_arns_for_cert_arns([
      "listener-arn-0/certificate-arn",
      "listener-arn-0/certificate-arn-0"
    ])
    assert results == {
      "listener-arn-0/certificate-arn": "listener-arn-0",
      "listener-arn-0/certificate-arn-0": "listener-arn-0"
    }

def test_get_matching_alb_listener_arns_for_multiple_listeners(alb):
    alb.expect_get_certificates_for_listener("listener-arn-0", 4)
    alb.expect_get_certificates_for_listener("listener-arn-1", 2)
    results = get_matching_alb_listener_arns_for_cert_arns([
      "listener-arn-0/certificate-arn-0",
      "listener-arn-0/certificate-arn-2",
      "listener-arn-1/certificate-arn-1",
    ])
    assert results == {
      "listener-arn-0/certificate-arn-0": "listener-arn-0",
      "listener-arn-0/certificate-arn-2": "listener-arn-0",
      "listener-arn-1/certificate-arn-1": "listener-arn-1"
    }