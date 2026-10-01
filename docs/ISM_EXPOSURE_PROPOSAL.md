# Optional ISM industry exposure proposals

Review proposal only, dated October 1, 2026. No entries are added to
config/industry_exposure.json. Exposure is not a direct assertion that an issuer's
results track an ISM industry ranking. Review current listing status, share-class
identity and at least 20 sessions of dollar volume before enabling any mapping.

| ISM industry | Candidate | Exposure rationale and issuer source | Liquidity / mapping caveat |
| --- | --- | --- | --- |
| Agriculture | ADM | Agricultural origination and processing connects ADM to farm output and agricultural demand. [Issuer](https://www.adm.com/en-us/about-adm/our-company/) | Processing/trading proxy, not a pure agricultural producer; also overlaps food manufacturing. |
| Construction | PWR | Quanta designs, builds and maintains utility and energy infrastructure. [Issuer](https://investors.quantaservices.com/company-information) | Specialized infrastructure construction rather than residential construction. |
| Management of companies | BRK.B | Berkshire owns and manages operating subsidiaries across many industries. [Issuer](https://www.berkshirehathaway.com/subs/sublinks.html) | Holding-company proxy with substantial insurance exposure; preserve the B share identity and verify provider symbol support. |
| Health care | HCA | HCA operates hospitals and care facilities. [Issuer](https://www.hcahealthcare.com/about) | Care-delivery exposure rather than pharmaceutical manufacturing; verify volume at review time. |
| Mining | FCX | Freeport operates copper mines with associated molybdenum and gold production. [Issuer](https://www.fcx.com/operations/north-america) | Metals/commodity concentration; not a broad mining index. |
| Printing | QUAD | Quad retains print production within its marketing services business. [Issuer](https://www.quad.com/about/our-story) | Smaller issuer and mixed marketing exposure; liquidity must be checked rather than assumed comparable to the large-cap candidates. |
| Textile mills | UFI | Unifi produces polyester/nylon performance fibers and recycled textile inputs. [Issuer](https://unifi.com/about-us/our-company) | Lower-liquidity exception, not a certified liquid large-cap choice. No equally direct large-cap US ticker is proposed; keep unmapped if liquidity is insufficient. |

ADM, PWR, BRK.B, HCA and FCX are the first review candidates. QUAD and UFI
need particularly careful liquidity review. Do not substitute a liquid apparel
retailer or uniform service company and label it a textile mill solely to fill
the map. Future config changes should be separately reviewed with issuer exposure,
source URL, review date and the existing sector ETF metadata.
