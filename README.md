# `google-dav-proxy`

A `{Cal,Card}DAV` proxy for Google.

Google is special in that it requires you to use OAuth2 to access CalDAV and
CardDAV. I implemented this to be able to use
[`pimsync`](https://pimsync.whynothugo.nl/) with my Google account, as it [does
not yet support OAuth2](https://todo.sr.ht/~whynothugo/pimsync/14).

I later learned that the author of `pimsync` actually proposed this exact idea
in [a blog
post](https://whynothugo.nl/journal/2025/03/04/design-for-google-caldav-support-in-pimsync/).
As far as I can tell, no one else has built this yet.

## Prerequisites

We depend on [`oama`](https://github.com/pdobsan/oama) to do the OAuth dance.

Here's an example `~/.config/oama/config.yaml` that works for CalDAV. Note the
`auth_scope`:

```yaml
encryption:
  encryption:
    tag: KEYRING
  services:
    google:
      auth_scope: https://mail.google.com/ https://www.googleapis.com/auth/calendar
      client_id: "this is (sort of) a secret"
      client_secret_cmd: "this is (sort of) another secret"
```

Once configured, run `oama authorize google me@gmail.com` (substituting with
your personal Gmail address) to do the OAuth flow.

## Usage

```console
$ google-dav-proxy me@gmail.com --bind localhost:8080
```

Where `me@gmail.com` is the Google Account address you set up with `oama`.

This works with the corresponding `pimsync` config file:

```scfg
storage cal_remote {
  type caldav
  # See "Calendar Paths" in
  # <https://whynothugo.nl/journal/2025/03/04/design-for-google-caldav-support-in-pimsync/#calendar-paths>.
  collection_id_segment second-last
  url http://localhost:8080/caldav/v2/
}
storage cal_local {
  type vdir/icalendar
  path ~/pim/calendars/jfly
}
pair cal {
  storage_a cal_local
  storage_b cal_remote
  collections all
}
```

## Notes

- This does not yet support `CardDAV`, but that should be a minor tweak.
