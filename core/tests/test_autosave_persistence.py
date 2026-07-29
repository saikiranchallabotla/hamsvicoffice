"""
Manual edits must survive without pressing Save.

Every module writes its live state into the session first; these tests cover
the second half — that the same edit also lands in the SavedWork the user is
working on, and that reopening a work does not inherit the previous one's
locations.

The views are called directly rather than through the test client so the
subscription middleware (which these endpoints sit behind in production) is
not part of what is being asserted.
"""

import json

import pytest
from django.contrib.auth.models import User

from core.models import Organization, Membership, SavedWork


class FakeSession(dict):
    """A session dict that tolerates `session.modified = True`."""
    modified = False


def _user_and_org(username):
    user = User.objects.create_user(username, password='x')
    org = Organization.objects.create(name=f'Org {username}', slug=f'org-{username}', owner=user)
    Membership.objects.create(user=user, organization=org, role='owner')
    return user, org


def _estimate(org, user, work_data=None):
    data = {
        'fetched_items': ['Concealed PVC Pipe'],
        'qty_map': {'Concealed PVC Pipe': '10'},
        'work_name': 'Original work name',
        'estimate_locations': [],
        'item_location_breakdown': {},
    }
    data.update(work_data or {})
    return SavedWork.objects.create(
        organization=org, user=user, name='E', work_type='new_estimate',
        category='electrical', work_data=data,
    )


def _request(rf, user, session=None, method='post', path='/', **kwargs):
    request = getattr(rf, method)(path, **kwargs)
    request.user = user
    request.session = FakeSession(session or {})
    return request


def _live_session(estimate, **extra):
    session = {
        'current_saved_work_id': estimate.id,
        'fetched_items': ['Concealed PVC Pipe'],
        'qty_map': {'Concealed PVC Pipe': '10'},
    }
    session.update(extra)
    return session


# ---------------------------------------------------------------- autosave --

@pytest.mark.django_db
def test_autosave_writes_the_live_session_into_the_linked_work(rf):
    from core.saved_works_views import autosave_current_work

    user, org = _user_and_org('autosave-writes')
    estimate = _estimate(org, user)

    request = _request(rf, user, _live_session(
        estimate,
        qty_map={'Concealed PVC Pipe': '25'},
        work_name='Edited without saving',
        estimate_locations=['Block A'],
        item_location_breakdown={'Concealed PVC Pipe': {'Block A': 25}},
    ))

    assert autosave_current_work(request, 'new_estimate') is not None

    estimate.refresh_from_db()
    assert estimate.work_data['qty_map'] == {'Concealed PVC Pipe': '25'}
    assert estimate.work_data['work_name'] == 'Edited without saving'
    assert estimate.work_data['estimate_locations'] == ['Block A']
    assert estimate.work_data['item_location_breakdown'] == {
        'Concealed PVC Pipe': {'Block A': 25}
    }


@pytest.mark.django_db
def test_autosave_refuses_to_blank_a_work_from_an_empty_session(rf):
    """A beacon fired after the session was cleared must not wipe saved data."""
    from core.saved_works_views import autosave_current_work

    user, org = _user_and_org('autosave-empty')
    estimate = _estimate(org, user)

    request = _request(rf, user, {
        'current_saved_work_id': estimate.id,
        'fetched_items': [],
    })

    assert autosave_current_work(request, 'new_estimate') is None
    estimate.refresh_from_db()
    assert estimate.work_data['qty_map'] == {'Concealed PVC Pipe': '10'}


@pytest.mark.django_db
def test_autosave_never_crosses_work_types(rf):
    """The estimate page must not flatten a workslip record it is linked to."""
    from core.saved_works_views import autosave_current_work

    user, org = _user_and_org('autosave-crosstype')
    estimate = _estimate(org, user)
    workslip = SavedWork.objects.create(
        organization=org, user=user, name='E - W1', work_type='workslip',
        category='electrical', parent=estimate, workslip_number=1,
        work_data={'ws_estimate_rows': [{'item_name': 'Concealed PVC Pipe'}]},
    )

    request = _request(rf, user, _live_session(
        workslip, qty_map={'Concealed PVC Pipe': '99'},
    ))

    assert autosave_current_work(request, 'new_estimate') is None
    workslip.refresh_from_db()
    assert workslip.work_data['ws_estimate_rows'] == [{'item_name': 'Concealed PVC Pipe'}]


@pytest.mark.django_db
def test_autosave_keeps_the_group_the_user_was_last_on(rf):
    """Autosave posts carry no 'group' field — it must not be blanked."""
    from core.saved_works_views import autosave_current_work

    user, org = _user_and_org('autosave-group')
    estimate = _estimate(org, user, work_data={'last_group': 'Points'})

    request = _request(rf, user, _live_session(
        estimate, qty_map={'Concealed PVC Pipe': '7'},
    ))

    assert autosave_current_work(request, 'new_estimate') is not None
    estimate.refresh_from_db()
    assert estimate.work_data['last_group'] == 'Points'
    assert estimate.work_data['qty_map'] == {'Concealed PVC Pipe': '7'}


@pytest.mark.django_db
def test_autosave_ignores_a_work_belonging_to_someone_else(rf):
    from core.saved_works_views import autosave_current_work

    owner, owner_org = _user_and_org('autosave-owner')
    intruder, _ = _user_and_org('autosave-intruder')
    estimate = _estimate(owner_org, owner)

    request = _request(rf, intruder, _live_session(
        estimate, qty_map={'Concealed PVC Pipe': '999'},
    ))

    assert autosave_current_work(request, 'new_estimate') is None
    estimate.refresh_from_db()
    assert estimate.work_data['qty_map'] == {'Concealed PVC Pipe': '10'}


# --------------------------------------------------------------- locations --

@pytest.mark.django_db
def test_saving_locations_persists_into_the_saved_work(rf):
    from core.views.project_views import save_locations

    user, org = _user_and_org('loc-save')
    estimate = _estimate(org, user)

    request = _request(
        rf, user, _live_session(estimate),
        path='/datas/electrical/locations/save/',
        data=json.dumps({'locations': ['Block A', 'Block B']}),
        content_type='application/json',
    )
    response = save_locations(request, 'electrical')
    assert json.loads(response.content)['status'] == 'ok'

    estimate.refresh_from_db()
    assert estimate.work_data['estimate_locations'] == ['Block A', 'Block B']


@pytest.mark.django_db
def test_saving_a_location_breakup_persists_into_the_saved_work(rf):
    from core.views.project_views import save_item_location_breakdown

    user, org = _user_and_org('loc-breakup')
    estimate = _estimate(org, user)

    request = _request(
        rf, user,
        _live_session(estimate, estimate_locations=['Block A', 'Block B']),
        path='/datas/electrical/item-location-breakdown/save/',
        data=json.dumps({
            'item': 'Concealed PVC Pipe',
            'breakdown': {'Block A': 4, 'Block B': 6},
        }),
        content_type='application/json',
    )
    response = save_item_location_breakdown(request, 'electrical')
    assert json.loads(response.content)['total'] == 10

    estimate.refresh_from_db()
    assert estimate.work_data['item_location_breakdown'] == {
        'Concealed PVC Pipe': {'Block A': 4, 'Block B': 6}
    }


@pytest.mark.django_db
def test_quantities_typed_on_the_page_persist_without_pressing_save(rf):
    from core.views.project_views import save_qty_map

    user, org = _user_and_org('qty-autosave')
    estimate = _estimate(org, user)

    request = _request(
        rf, user, _live_session(estimate),
        path='/datas/electrical/save_qty_map/',
        data={
            'qty_map': json.dumps({'Concealed PVC Pipe': '42'}),
            'unit_map': json.dumps({'Concealed PVC Pipe': 'Mtrs'}),
            'work_name': 'Typed but never saved',
            'grand_total': '5000',
        },
    )
    response = save_qty_map(request, 'electrical')
    assert json.loads(response.content)['status'] == 'ok'

    estimate.refresh_from_db()
    assert estimate.work_data['qty_map'] == {'Concealed PVC Pipe': '42'}
    assert estimate.work_data['work_name'] == 'Typed but never saved'
    assert estimate.work_data['grand_total'] == '5000'


@pytest.mark.django_db
def test_resuming_a_work_does_not_inherit_the_previous_works_locations(rf):
    """Locations are per estimate — an empty list must clear, not leave stale."""
    from core.saved_works_views import restore_work_data

    user, org = _user_and_org('loc-restore')
    with_locations = _estimate(org, user, work_data={
        'estimate_locations': ['Block A'],
        'item_location_breakdown': {'Concealed PVC Pipe': {'Block A': 3}},
    })
    without_locations = _estimate(org, user)

    request = _request(rf, user, {}, method='get')

    restore_work_data(request, with_locations)
    assert request.session['estimate_locations'] == ['Block A']

    restore_work_data(request, without_locations)
    assert request.session['estimate_locations'] == []
    assert request.session['item_location_breakdown'] == {}


# ---------------------------------------------------------------- download --

@pytest.mark.django_db
def test_download_takes_the_locations_the_page_posts(rf):
    """
    The Break-up sheet is built from the session copy. The page posts its own
    (localStorage-backed) copy with the download, which must win so the sheet
    is still written after a session eviction.
    """
    from core.views.project_views import download_output

    user, org = _user_and_org('download-locations')
    breakdown = {'Concealed PVC Pipe': {'Block A': 4, 'Block B': 6}}

    request = _request(
        rf, user,
        {'fetched_items': ['Concealed PVC Pipe']},   # session lost the locations
        path='/datas/electrical/download/',
        data={
            'fetched_items': json.dumps(['Concealed PVC Pipe']),
            'qty_map': json.dumps({'Concealed PVC Pipe': '10'}),
            'estimate_locations_json': json.dumps(['Block A', 'Block B']),
            'item_location_breakdown_json': json.dumps(breakdown),
        },
    )

    # Excel generation needs a backend workbook; only the parsing that happens
    # before it is under test here.
    try:
        download_output(request, 'electrical')
    except Exception:
        pass

    assert request.session['estimate_locations'] == ['Block A', 'Block B']
    assert request.session['item_location_breakdown'] == breakdown
