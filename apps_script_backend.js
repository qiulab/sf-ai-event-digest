/**
 * SF AI Event Digest — Subscriber Backend
 *
 * Deploy as a Google Apps Script Web App:
 * 1. Open https://script.google.com/home  
 * 2. New Project → paste this code  
 * 3. Click "Deploy" → "New Deployment" → Type: Web App  
 * 4. Execute as: Me | Who has access: Anyone  
 * 5. Copy the Web App URL and paste into SCRIPT_URL in index.html  
 */

// ── Config ────────────────────────────────────────────────────
const SHEET_URL = 'https://docs.google.com/spreadsheets/d/1qVVEYTHxhRltcTb3N3T8FSgjS04wkaPT0hao4nM0jjM/edit';
const SHEET_TAB = 'subscribers';
const FROM_NAME = 'SF AI Event Digest';

// ── Handle POST (subscribe form) ──────────────────────────────
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const email = (data.email || '').trim();
    if (!email) return jsonResponse({ ok: false, error: 'No email' });

    // 1. Append to subscribers sheet
    appendSubscriber(data);

    // 2. Send immediate welcome + events email
    sendImmediateEmail(email, data.role || '', data.interests || '');

    return jsonResponse({ ok: true });
  } catch (err) {
    return jsonResponse({ ok: false, error: err.toString() });
  }
}

function doGet(e) {
  // Health check
  return jsonResponse({ ok: true, status: 'SF AI Event Digest backend running' });
}

// ── Append subscriber to sheet ────────────────────────────────
function appendSubscriber(data) {
  const ss = SpreadsheetApp.openByUrl(SHEET_URL);
  const sheet = ss.getSheetByName(SHEET_TAB) || ss.getSheets()[0];
  sheet.appendRow([
    '',                                    // name (optional, not collected)
    (data.email || '').trim(),
    'San Francisco',                       // city default
    data.role || '',
    data.interests || '',
    'Weekly',                              // frequency hardcoded
    data.event_types || '',               // new: event type preferences
    new Date().toISOString(),             // subscribed_at
  ]);
}

// ── Send immediate welcome email ──────────────────────────────
function sendImmediateEmail(email, role, interests) {
  const subject = "You're in! Your SF AI Events This Week 🤖";
  const body = buildEmailHtml(role, interests);
  GmailApp.sendEmail(email, subject, '', {
    htmlBody: body,
    name: FROM_NAME,
  });
}

// ── Build email HTML ──────────────────────────────────────────
function buildEmailHtml(role, interests) {
  const greeting = role ? \`Welcome, \${role}!\` : "Welcome!";
  const interestLine = interests
    ? \`<p style="margin:0 0 20px;color:#555;font-size:14px">Matched to your interests: <strong>\${interests}</strong></p>\`
    : '';

  return \`<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f8f8f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f8f8;padding:32px 16px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,0.08)">

        <tr><td style="background:linear-gradient(135deg,#5b5ef4,#7c3aed);padding:32px 40px;text-align:center">
          <h1 style="margin:0;font-size:24px;color:#fff;font-weight:700">🤖 SF AI Events</h1>
          <p style="margin:8px 0 0;color:#d4d4ff;font-size:14px">Your personalized weekly digest</p>
        </td></tr>

        <tr><td style="padding:32px 40px 0">
          <h2 style="margin:0 0 8px;font-size:20px;color:#1a1a1a">\${greeting}</h2>
          <p style="margin:0 0 6px;color:#555;font-size:14px">Here are this week's top AI events in San Francisco:</p>
          \${interestLine}
        </td></tr>

        <tr><td style="padding:0 40px 28px">
          <table width="100%" cellpadding="0" cellspacing="0">
            
        <tr>
          <td style="padding:18px 0;border-bottom:1px solid #f0f0f0">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td><p style="margin:0 0 2px;font-size:11px;color:#888">1 of 7</p>
                    <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:#1a1a1a">AMD Developer Hackathon</p></td>
                <td align="right" valign="top">
                  <span style="background:#be185d;color:#fff;padding:3px 10px;border-radius:100px;font-size:12px;font-weight:700">10/10</span>
                </td>
              </tr>
            </table>
            <p style="margin:4px 0 6px;font-size:12px;color:#777">📅 Mon, May 04 · 09:00 AM PDT &nbsp;·&nbsp; 📍 San Francisco, CA</p>
            <p style="margin:0 0 6px;font-size:12px;color:#666">⭐ Mistral · ⭐ Hugging Face</p>
            <p style="margin:0 0 10px;font-size:13px;color:#444;line-height:1.5">AMD Developer Hackathon | Lablab.ai About The AMD Developer Hackathon is a hands-on event for developers, founders, engineers, and builders who want to push what’s possible with AI</p>
            <a href="https://lablab.ai/ai-hackathons/amd-developer" style="display:inline-block;padding:7px 16px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:7px;font-size:13px;font-weight:600">RSVP →</a>
          </td>
        </tr>
        <tr>
          <td style="padding:18px 0;border-bottom:1px solid #f0f0f0">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td><p style="margin:0 0 2px;font-size:11px;color:#888">2 of 7</p>
                    <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:#1a1a1a">AI Meetup</p></td>
                <td align="right" valign="top">
                  <span style="background:#be185d;color:#fff;padding:3px 10px;border-radius:100px;font-size:12px;font-weight:700">10/10</span>
                </td>
              </tr>
            </table>
            <p style="margin:4px 0 6px;font-size:12px;color:#777">📅 Tue, May 05 · 05:00 PM PDT &nbsp;·&nbsp; 📍 San Francisco, CA</p>
            <p style="margin:0 0 6px;font-size:12px;color:#666">⭐ Cursor · ⭐ Together AI</p>
            <p style="margin:0 0 10px;font-size:13px;color:#444;line-height:1.5">Join Pinecone & The Gen Academy for a high-energy AI meetup in the San Francisco Bay Area (Menlo Ventures office in SoMa).</p>
            <a href="https://luma.com/5lms9659" style="display:inline-block;padding:7px 16px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:7px;font-size:13px;font-weight:600">RSVP →</a>
          </td>
        </tr>
        <tr>
          <td style="padding:18px 0;border-bottom:1px solid #f0f0f0">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td><p style="margin:0 0 2px;font-size:11px;color:#888">3 of 7</p>
                    <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:#1a1a1a">Transformers vs. Post-Transformers: The Deciding Round with Lukasz Kaiser</p></td>
                <td align="right" valign="top">
                  <span style="background:#be185d;color:#fff;padding:3px 10px;border-radius:100px;font-size:12px;font-weight:700">10/10</span>
                </td>
              </tr>
            </table>
            <p style="margin:4px 0 6px;font-size:12px;color:#777">📅 Tue, May 05 · 05:00 PM PDT &nbsp;·&nbsp; 📍 San Francisco, CA</p>
            <p style="margin:0 0 6px;font-size:12px;color:#666">⭐ OpenAI · ⭐ AWS</p>
            <p style="margin:0 0 10px;font-size:13px;color:#444;line-height:1.5">Lukasz Kaiser, co-inventor of the Transformer, is stepping into the ring for the most gloriously nerdy showdown in SF: a live, tongue-in-cheek Transformers vs. Post-Transformers bo</p>
            <a href="https://luma.com/post-transformer-sf" style="display:inline-block;padding:7px 16px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:7px;font-size:13px;font-weight:600">RSVP →</a>
          </td>
        </tr>
        <tr>
          <td style="padding:18px 0;border-bottom:1px solid #f0f0f0">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td><p style="margin:0 0 2px;font-size:11px;color:#888">4 of 7</p>
                    <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:#1a1a1a">Women Shaping the Future of AI in Law | micro1 & Women in AI</p></td>
                <td align="right" valign="top">
                  <span style="background:#be185d;color:#fff;padding:3px 10px;border-radius:100px;font-size:12px;font-weight:700">10/10</span>
                </td>
              </tr>
            </table>
            <p style="margin:4px 0 6px;font-size:12px;color:#777">📅 Wed, May 06 · 06:00 PM PDT &nbsp;·&nbsp; 📍 San Francisco, CA</p>
            <p style="margin:0 0 6px;font-size:12px;color:#666">⭐ Anthropic · ⭐ Harvey</p>
            <p style="margin:0 0 10px;font-size:13px;color:#444;line-height:1.5">Join micro1 and Women in AI for an evening with founders and operators leading the charge in AI for legal.</p>
            <a href="https://luma.com/8tepkh7r" style="display:inline-block;padding:7px 16px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:7px;font-size:13px;font-weight:600">RSVP →</a>
          </td>
        </tr>
        <tr>
          <td style="padding:18px 0;border-bottom:1px solid #f0f0f0">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td><p style="margin:0 0 2px;font-size:11px;color:#888">5 of 7</p>
                    <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:#1a1a1a">Agentic + AI Coding Night</p></td>
                <td align="right" valign="top">
                  <span style="background:#be185d;color:#fff;padding:3px 10px;border-radius:100px;font-size:12px;font-weight:700">10/10</span>
                </td>
              </tr>
            </table>
            <p style="margin:4px 0 6px;font-size:12px;color:#777">📅 Thu, May 07 · 03:30 PM PDT &nbsp;·&nbsp; 📍 San Francisco, CA</p>
            <p style="margin:0 0 6px;font-size:12px;color:#666">⭐ Anthropic · ⭐ OpenAI</p>
            <p style="margin:0 0 10px;font-size:13px;color:#444;line-height:1.5">Join us for another Agentic + AI Coding Night on Thursday, May 7 from 3:30pm - 9:00pm PST in SF for a multi-track deep dive into the architecture of autonomous coding agents.</p>
            <a href="https://luma.com/agenticaiobsnightsf-5-7" style="display:inline-block;padding:7px 16px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:7px;font-size:13px;font-weight:600">RSVP →</a>
          </td>
        </tr>
        <tr>
          <td style="padding:18px 0;border-bottom:1px solid #f0f0f0">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td><p style="margin:0 0 2px;font-size:11px;color:#888">6 of 7</p>
                    <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:#1a1a1a">Nozomio Hackathon</p></td>
                <td align="right" valign="top">
                  <span style="background:#be185d;color:#fff;padding:3px 10px;border-radius:100px;font-size:12px;font-weight:700">10/10</span>
                </td>
              </tr>
            </table>
            <p style="margin:4px 0 6px;font-size:12px;color:#777">📅 Sat, May 09 · 08:00 AM PDT &nbsp;·&nbsp; 📍 San Francisco, CA</p>
            <p style="margin:0 0 6px;font-size:12px;color:#666">⭐ Vercel · ⭐ Y Combinator</p>
            <p style="margin:0 0 10px;font-size:13px;color:#444;line-height:1.5">Build the Future of AI Agents The hottest hackathon in the city sponsored by Nia and many more. Join us on the 9th of May in San Francisco at the EF office for a not-so-boring even</p>
            <a href="https://luma.com/rshibq6i" style="display:inline-block;padding:7px 16px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:7px;font-size:13px;font-weight:600">RSVP →</a>
          </td>
        </tr>
        <tr>
          <td style="padding:18px 0;border-bottom:1px solid #f0f0f0">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td><p style="margin:0 0 2px;font-size:11px;color:#888">7 of 7</p>
                    <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:#1a1a1a">Open Source Computer Use Hackathon</p></td>
                <td align="right" valign="top">
                  <span style="background:#be185d;color:#fff;padding:3px 10px;border-radius:100px;font-size:12px;font-weight:700">10/10</span>
                </td>
              </tr>
            </table>
            <p style="margin:4px 0 6px;font-size:12px;color:#777">📅 Sat, May 09 · 10:00 AM PDT &nbsp;·&nbsp; 📍 San Francisco, CA</p>
            <p style="margin:0 0 6px;font-size:12px;color:#666">⭐ Anthropic · ⭐ NVIDIA</p>
            <p style="margin:0 0 10px;font-size:13px;color:#444;line-height:1.5">We’re inviting an exclusive group of local builders to spend a day at the first computer use hackathon in San Francisco. Join us to build cool projects with open source AI & comput</p>
            <a href="https://luma.com/cua" style="display:inline-block;padding:7px 16px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:7px;font-size:13px;font-weight:600">RSVP →</a>
          </td>
        </tr>
          </table>
        </td></tr>

        <tr><td style="background:#f8f8f8;padding:20px 40px;text-align:center;border-top:1px solid #eee">
          <p style="margin:0;font-size:12px;color:#999">
            SF AI Event Digest · Every Monday at 8am Pacific<br>
            <a href="#" style="color:#999">Unsubscribe</a>
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body></html>\`;
}

// ── Helpers ───────────────────────────────────────────────────
function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
