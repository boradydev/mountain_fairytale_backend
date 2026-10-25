"""Create the initial GlitchTip administrator/projects without printing a password."""

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path


SETUP = """
import os,sys,json,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','glitchtip.settings')
django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from allauth.account.models import EmailAddress
from apps.organizations_ext.models import Organization,OrganizationUser,OrganizationOwner
from apps.organizations_ext.constants import OrganizationUserRole
from apps.teams.models import Team
from apps.projects.models import Project,ProjectKey
values=json.load(sys.stdin)
with transaction.atomic():
    user,created=get_user_model().objects.get_or_create(email=values['email'])
    if created:
        user.set_password(values['password'])
        user.is_staff=True
        user.is_superuser=True
        user.save()
    EmailAddress.objects.update_or_create(user=user,email=user.email,defaults={'primary':True,'verified':True})
    org,_=Organization.objects.get_or_create(slug='mountain-fairytale',defaults={'name':'Mountain Fairytale'})
    member,_=OrganizationUser.objects.get_or_create(organization=org,user=user,
        defaults={'role':OrganizationUserRole.OWNER})
    OrganizationOwner.objects.get_or_create(organization=org,defaults={'organization_user':member})
    team,_=Team.objects.get_or_create(organization=org,slug='support')
    team.members.add(member)
    projects=[]
    for name,platform in [('backend','python-fastapi'),('flutter','flutter'),('operations','other')]:
        project,_=Project.objects.get_or_create(organization=org,slug=name,
            defaults={'name':name,'platform':platform})
        team.projects.add(project)
        key=ProjectKey.objects.filter(project=project,is_active=True).first()
        projects.append({'slug':name,'id':project.pk,'publicKey':key.public_key.hex,'dsn':key.get_dsn()})
print(json.dumps({'administratorCreated':created,'projects':projects}))
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--project", type=Path, default=Path("/opt/mountain-fairytale"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run as root")
    state = args.project / ".deploy"
    state.mkdir(mode=0o700, exist_ok=True)
    password_file = state / "monitoring-admin-initial.password"
    if not password_file.exists():
        descriptor = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(secrets.token_urlsafe(24) + "\n")
    result = subprocess.run(
        ["docker", "exec", "-i", "mountain-fairytale-monitoring-web-1", "python", "-c", SETUP],
        input=json.dumps({"email": args.email, "password": password_file.read_text().strip()}),
        capture_output=True, text=True,
    )
    if result.returncode:
        raise SystemExit("GlitchTip setup failed; no password or input was printed")
    metadata = json.loads(result.stdout.strip().splitlines()[-1])
    output = state / "monitoring-projects.json"
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(metadata, stream, indent=2)
    print("Administrator/projects prepared; existing passwords preserved")
    print(f"Initial password (root only): {password_file}")
    print(f"Project metadata (root only): {output}")


if __name__ == "__main__":
    main()
