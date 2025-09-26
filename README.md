# `google-dav-proxy`

A `{Cal,Card}DAV` proxy for Google.

Google is special in that it requires you to use OAuth2 to access CalDAV
and CardDAV. I implemented this to be able to use `pimsync` with my Google
account, as it [does not yet support OAuth2](https://todo.sr.ht/~whynothugo/pimsync/14).

I later learned that the author of `pimsync` actually proposed this exact idea
in [a blog
post](https://whynothugo.nl/journal/2025/03/04/design-for-google-caldav-support-in-pimsync/).
As far as I can tell, no one else has built this yet.
