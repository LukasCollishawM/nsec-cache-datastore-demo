# NSEC Cache Datastore Demo

This project demonstrates a surprising and underexplored property of DNSSEC resolvers:

> **Validating resolvers can derive and serve structured information for domain names that were never queried, using only cached denial-of-existence proofs (NSEC) and aggressive negative caching (RFC 8198).**

In other words, information can exist *only inside resolver caches* and still be meaningfully queried.

This repository provides a fully reproducible local lab that proves this behavior empirically.

---

## What this demonstrates

DNSSEC NSEC records form a signed, ordered linked list of domain names.
With **RFC 8198 aggressive negative caching**, validating resolvers may:

* cache NSEC proofs from a single NXDOMAIN response
* later **synthesize NXDOMAIN answers for different, previously unseen names**
* without contacting the authoritative server again

This demo exploits that property to encode data into **NSEC “next name” pointers**, effectively creating a:

> **Read-only, cache-resident disclosure plane inside DNS resolvers**

The authoritative server is involved only during priming. Subsequent reads are resolved entirely from the resolver cache.

---

Key properties:

* No data is stored in TXT or answer payloads
* Data is encoded in *zone structure*, not responses
* Resolvers compute answers they never received
* Authoritative logs do **not** reflect all disclosures
* State exists transiently and only in intermediaries

This reframes resolvers as **computational actors**, not passive caches.

---

## Architecture (local lab)

```
client ──► validating resolver (Unbound, RFC8198 enabled)
                  │
                  └──► authoritative server (DNSSEC-signed NSEC zone)
```

* The authoritative server hosts a DNSSEC-signed zone using **NSEC (not NSEC3)**.
* The resolver validates responses and aggressively caches NSEC proofs.
* The client:

  * primes the cache by walking the NSEC chain
  * later queries different in-gap names
  * proves that no additional authoritative queries occur

Everything runs locally via Docker Compose.

---

## What the demo proves

The demo shows, with logs and counters:

* A resolver answering NXDOMAIN for names it never queried
* Those answers containing NSEC proofs revealing encoded payload
* Authoritative query count remaining unchanged during verification (Δ = 0)

This demonstrates **cache-resident inference**, not storage.

---

## Limitations (important)

This is:

* ephemeral (TTL-bound)
* read-only
* policy- and implementation-dependent
* not a vulnerability or exploit

---

## Related work

If you’re interested in the *general pattern* behind this result, see:

**Cache Algebra Demo**
[https://github.com/LukasCollishawM/cache-algebra-demo](https://github.com/LukasCollishawM/cache-algebra-demo)

That project explores how caches in general (HTTP, CDNs) act as hidden state machines that compute results via eviction dynamics. The two demos are independent but share the same underlying idea: **cache-resident computation**.

---

## Running the demo

See the full instructions in this repository’s README sections:

```bash
make demo
```

Expected output includes:

* decoded payload
* authoritative query counts before/after
* a verdict confirming resolver-side synthesis

---

## Ethics & scope

This demo runs entirely in a controlled local environment.
Do not probe public resolvers or third-party infrastructure without permission.

The purpose is to understand protocol behavior, not to abuse it.
