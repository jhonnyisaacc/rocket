# ISM acquisition coverage

The issuer's PR Newswire archive is the primary discovery source. The official
ISM sitemap/roundup is a fallback, in the order specified in config/providers.toml.
Only fetched release content supplies PMI and industry rankings; URLs never supply
numeric evidence. Kind, reference month and publication eligibility must agree.

On October 1, 2026, local inspection found the August manufacturing roundup returning
unusable HTTP-200 content and the services roundup returning HTTP 404. VPS behavior
varied: services recovered through official discovery and September manufacturing
through PR Newswire. The official path is therefore retained, without assuming it
is reliably accessible. InvalidProviderData denotes unusable content;
UnsupportedEndpoint denotes an unsupported/missing HTTP endpoint. Reports expose
provider_attempts and retain provider_failures. Successful fallback is PARTIAL,
not an overall acquisition failure; direct complete primary acquisition is HEALTHY.

## VPS verification

```bash
set -a && source /home/david/nave/.env && set +a
/home/david/rocket/.venv/bin/rocket ism --json
/home/david/rocket/.venv/bin/rocket shorts --json
```

Run ISM before shorts to populate the shared candidate inputs. Use --state-dir with
an isolated directory for review. Check CURRENT identities, individual attempts,
HEALTHY/PARTIAL recovered reports, and execution_enabled=false. Credentials are
process environment only; Rocket never loads dotenv files.
