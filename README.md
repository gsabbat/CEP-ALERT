# CEP Haiti candidate tracker

This tracker checks the CEP candidate dashboard (https://tableau.cephaiti.ht) every 10 minutes. It sends you an alert when a name is added to or removed from:

- President (national)
- Senator, Sud-Est
- Deputy, Sud-Est

Alerts for President are sent as high priority. The tracker runs for free on GitHub, so your computer does not need to stay on.

## Setup (about 15 minutes)

### 1. Put the files on GitHub
1. Create a free account at github.com if you do not have one.
2. Create a new repository (for example `cep-tracker`). It can be private.
3. Upload all the files from this folder, including the `.github` folder and the `state` folder.
   Tip: the easiest way is to drag the files into the "uploading an existing file" page. If the `.github` folder does not upload, create the file `.github/workflows/track.yml` by hand with "Add file > Create new file" and paste in its content.

### 2. Choose how you get alerts
You can use one or both options.

**Option A: push alert on your phone (easiest)**
1. Install the free **ntfy** app (iPhone App Store or Google Play).
2. In the app, tap "+" and subscribe to a topic. Pick a long name that is hard to guess, such as `cep-giscard-7h3k9`. Anyone who knows the name can read the alerts, so do not use a simple one.

**Option B: email (and text message through email)**
1. You need a Gmail account with 2-step verification turned on.
2. Go to https://myaccount.google.com/apppasswords and create an app password. Copy the 16 letters.
3. To also get a text message, add your carrier's email-to-SMS address in `EMAIL_TO`, for example:
   - T-Mobile: `5551234567@tmomail.net`
   - Verizon: `5551234567@vtext.com`
   - AT&T: `5551234567@txt.att.net`
   (Some carriers have stopped supporting this. The ntfy app is more reliable.)

### 3. Add your settings to GitHub
In your repository, go to **Settings > Secrets and variables > Actions > New repository secret** and add:

| Secret name     | Value                                   | Needed for |
|-----------------|-----------------------------------------|------------|
| `NTFY_TOPIC`    | your ntfy topic name                    | Option A   |
| `SMTP_USER`     | your Gmail address                      | Option B   |
| `SMTP_PASSWORD` | the 16-letter app password              | Option B   |
| `EMAIL_TO`      | where to send, comma-separated          | Option B   |

### 4. Start it
1. Go to the **Actions** tab. If GitHub asks, click to enable workflows.
2. Click **CEP candidate tracker**, then **Run workflow**.
3. Within a minute you should get a "CEP tracker is running" alert with the current counts. After that it runs on its own every 10 minutes.

## Good to know
- The first run compares the President list with the 33 names seen on 15/11/2026 at 8:22 PM, so any name added after that is reported right away.
- GitHub sometimes starts scheduled runs 5 to 20 minutes late when it is busy.
- GitHub pauses scheduled runs after 60 days with no activity in the repository. The tracker commits a change each time the list changes, which counts as activity.
- The CEP says the dashboard data is preliminary. Names can also be removed during verification, so you get an alert for removals too.
- To change which lists are watched, add an env line `WATCH: president` (or `president,senateur_se,depute_se`) in `.github/workflows/track.yml`.
- To stop the tracker, go to **Actions > CEP candidate tracker > ... > Disable workflow**.

## Run it on your own computer (optional)
```
NTFY_TOPIC=your-topic python3 tracker.py
```
Python 3.8 or newer. No extra packages needed.
