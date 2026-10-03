"""Blast radius: what a compromised account could reach in the simulated org.

The graph is employee → identity provider → the services the employee has
access to → the data stored in them, plus the colleagues reachable from the
mailbox. Every service is returned; `at_risk` marks the reachable ones.
"""

from app.schemas import (
    BlastRadius,
    BlastRadiusEdge,
    BlastRadiusNode,
    Organization,
    ServiceKind,
)

COLLEAGUES_NODE_ID = "colleagues"


def compute_blast_radius(organization: Organization, employee_id: str) -> BlastRadius:
    employees_by_id = {employee.id: employee for employee in organization.employees}
    if employee_id not in employees_by_id:
        raise KeyError(employee_id)
    employee = employees_by_id[employee_id]
    first_name = employee.name.split()[0]
    services_by_id = {service.id: service for service in organization.services}
    identity_provider = next(s for s in organization.services if s.kind == ServiceKind.IDENTITY_PROVIDER)

    # Which service stores each data set, e.g. "payroll_data" -> "hr_portal".
    parent_service_id_by_data_id = {
        dependency.target: dependency.source
        for dependency in organization.dependencies
        if services_by_id[dependency.target].kind == ServiceKind.DATA
    }
    reachable_service_ids = {identity_provider.id, *employee.access}
    reachable_service_ids |= {
        data_id for data_id, parent_id in parent_service_id_by_data_id.items() if parent_id in reachable_service_ids
    }

    nodes = [BlastRadiusNode(
        id=employee.id,
        label=employee.name,
        kind="employee",
        at_risk=True,
        reason=f"{employee.name}'s account may be compromised.",
    )]
    for service in organization.services:
        reachable = service.id in reachable_service_ids
        nodes.append(BlastRadiusNode(
            id=service.id,
            label=service.name,
            kind=_node_kind(service.kind),
            sensitivity=service.sensitivity,
            at_risk=reachable,
            reason=_reason(service, reachable, first_name, services_by_id, parent_service_id_by_data_id),
        ))

    mailbox_reachable = any(services_by_id[s].kind == ServiceKind.EMAIL for s in reachable_service_ids)
    colleague_count = len(organization.employees) - 1
    nodes.append(BlastRadiusNode(
        id=COLLEAGUES_NODE_ID,
        label=f"Colleagues ({colleague_count})",
        kind="people",
        at_risk=mailbox_reachable,
        reason=(
            f"From {first_name}'s mailbox an attacker could send convincing phishing to {colleague_count} colleagues."
            if mailbox_reachable else f"{first_name} has no company mailbox."
        ),
    ))

    edges = [BlastRadiusEdge(source=employee.id, target=identity_provider.id, relation="signs in with")]
    edges += [
        BlastRadiusEdge(source=dependency.source, target=dependency.target, relation=dependency.relation)
        for dependency in organization.dependencies
    ]
    edges += [
        BlastRadiusEdge(source=service.id, target=COLLEAGUES_NODE_ID, relation="can email")
        for service in organization.services if service.kind == ServiceKind.EMAIL
    ]

    reachable_apps = [
        services_by_id[s].name for s in services_by_id
        if s in reachable_service_ids and services_by_id[s].kind not in (ServiceKind.DATA, ServiceKind.IDENTITY_PROVIDER)
    ]
    reachable_data = [
        services_by_id[s].name for s in services_by_id
        if s in reachable_service_ids and services_by_id[s].kind == ServiceKind.DATA
    ]
    explanation = (
        f"If {employee.name}'s account is compromised, an attacker may be able to sign in to "
        f"{_join(reachable_apps)} through single sign-on"
        + (f", and from there reach {_join(reachable_data)}" if reachable_data else "")
        + ". This shows what the account can access, not what was accessed. "
        "Protecting the password and active sessions quickly is recommended."
    )

    return BlastRadius(
        employee_id=employee.id,
        nodes=nodes,
        edges=edges,
        affected_service_ids=[s for s in services_by_id if s in reachable_service_ids],
        explanation=explanation,
    )


def _node_kind(kind: ServiceKind) -> str:
    if kind == ServiceKind.IDENTITY_PROVIDER:
        return "identity_provider"
    if kind == ServiceKind.DATA:
        return "data"
    return "service"


def _reason(service, reachable, first_name, services_by_id, parent_service_id_by_data_id) -> str:
    if service.kind == ServiceKind.IDENTITY_PROVIDER:
        return f"{first_name} signs in to every company service here, so the password opens it."
    if service.kind == ServiceKind.DATA:
        parent_name = services_by_id[parent_service_id_by_data_id[service.id]].name
        if reachable:
            return f"Stored in {parent_name}, which {first_name} can open."
        return f"Stored in {parent_name}, which {first_name} cannot open."
    if reachable:
        return f"{first_name} has access to {service.name} through single sign-on."
    return f"{first_name} has no access to {service.name}."


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]
