/**
 * Creates the Wapas Nahi customer survey in your Google Drive.
 *
 * How to use (2 minutes):
 *  1. Go to https://script.google.com  ->  New project
 *  2. Delete the sample code, paste this whole file, click Save.
 *  3. Choose the function `createCustomerSurvey` in the toolbar and click Run.
 *     Approve the permission prompt (it only creates forms in your own Drive).
 *  4. The Execution log at the bottom prints the edit link and the share link.
 *  Run it from the editor only. Do NOT use Deploy -> Web app (that gives 'Script function not found: doGet').
 *
 * IMPORTANT: the question codes (A1, B3, C2 ...) at the start of each title are used by
 * step2_prepare/05_survey_analysis.py to read the responses. Keep them if you edit wording.
 */

var SCALE = ['Definitely yes', 'Probably yes', 'Probably not', 'Definitely not'];

function mc_(form, title, choices, required, help) {
  var item = form.addMultipleChoiceItem().setTitle(title).setChoiceValues(choices).setRequired(required !== false);
  if (help) item.setHelpText(help);
  return item;
}

function cb_(form, title, choices, required, help) {
  var item = form.addCheckboxItem().setTitle(title).setChoiceValues(choices).setRequired(required !== false);
  if (help) item.setHelpText(help);
  return item;
}

function createCustomerSurvey() {
  var form = FormApp.create('Online shopping and deliveries: a 4-minute survey');
  form.setDescription(
    'We are a student team at IIT Kanpur researching why online orders sometimes do not get delivered, ' +
    'and how to fix it. The survey is anonymous and takes about 4 minutes. ' +
    'There are no right or wrong answers; please answer based on what you actually do.');
  form.setCollectEmail(false);
  form.setProgressBar(true);
  form.setConfirmationMessage('Thank you! Your answers help us design better deliveries.');

  // ---------- Section A: About you
  mc_(form, 'A1. Your age', ['Under 18', '18-24', '25-34', '35-49', '50 or above']);
  mc_(form, 'A2. Where do you live?', ['Metro city (Delhi, Mumbai, Bengaluru, etc.)',
      'Other large city (e.g. Kanpur, Lucknow, Indore)', 'Small town', 'Village']);
  var a3 = form.addMultipleChoiceItem().setTitle('A3. How often do you order something online?').setRequired(true);
  mc_(form, 'A4. Have you ordered from Meesho?', ['Yes, often', 'Yes, a few times', 'No']);
  mc_(form, 'A5. How do you usually pay for online orders?', ['Almost always cash on delivery (COD)',
      'A mix of COD and online payment', 'Almost always online payment (UPI, card)']);
  cb_(form, 'A6. What do you buy online most often? (up to 3)', ['Clothing', 'Footwear', 'Home and kitchen',
      'Beauty and personal care', 'Electronics and accessories', 'Other']);

  // ---------- Section B gate
  var pageB = form.addPageBreakItem().setTitle('Parcels that did not reach you');
  var b1 = form.addMultipleChoiceItem()
      .setTitle('B1. In the last 12 months, has a parcel you ordered gone back without being delivered?')
      .setRequired(true);
  mc_(form, 'B2. How many times in the last 12 months?', ['Once', '2-3 times', '4 or more times']);
  var b3 = mc_(form, 'B3. Think about the most recent time. What was the main reason?', [
      'I did not have cash at that moment',
      'I changed my mind or found it cheaper elsewhere',
      'It took too long and I did not need it any more',
      'Someone in my family did not want me to take it',
      'The size or item did not look right',
      'I was not home or could not take the call',
      'I asked them to come another day, but it went back',
      'The delivery person could not find my address',
      'The delivery person never actually came, but it was marked as attempted',
      'I did not place that order']);
  b3.showOtherOption(true);
  mc_(form, 'B4. How had you paid for that order?', ['Cash on delivery', 'Paid online', 'Do not remember']);
  mc_(form, 'B5. How many days after ordering did it arrive (or was supposed to arrive)?',
      ['1-3 days', '4-7 days', '8-14 days', 'More than 14 days', 'Do not remember']);
  cb_(form, 'B6. Would any of these have helped you accept that parcel?', [
      'Paying by UPI at the door instead of cash', 'Choosing a new delivery date myself',
      'Leaving it with a neighbour or a nearby shop', 'Sending my exact location on WhatsApp',
      'Exchanging for another size on the spot', 'A WhatsApp message before dispatch to confirm or cancel',
      'None of these']);

  // ---------- Section C: door fixes (one question per fix, mobile friendly)
  var pageC = form.addPageBreakItem().setTitle('Delivery options')
      .setHelpText('For each one, imagine it is a cash-on-delivery order you still want.');
  mc_(form, 'C1. You do not have cash when the parcel arrives. Would you pay by UPI at the door?', SCALE);
  mc_(form, 'C2. You will not be home today. Would you pick a new delivery date on WhatsApp?', SCALE);
  mc_(form, 'C3. You are not home. Would you be fine with it being left with a neighbour or a kirana within 1 km?', SCALE);
  mc_(form, 'C4. The rider cannot find your address. Would you send your exact location on WhatsApp?', SCALE);
  mc_(form, 'C5. The size looks wrong. Would you accept a free exchange instead of refusing it?', SCALE);

  // ---------- Section D: buying a parcel someone else refused
  form.addPageBreakItem().setTitle('Reselling refused parcels').setHelpText(
      'Sometimes a customer refuses a parcel. Instead of sending it all the way back to the seller, it could be ' +
      'kept at a local delivery centre and sent to the next person nearby who orders the exact same item. ' +
      'The parcel is still sealed and has never been opened.');
  mc_(form, 'D1. If your order came this way, would you be okay receiving it?', [
      'Yes, no problem', 'Yes, if it is sealed and has passed a check', 'Only if I got a small discount', 'No']);
  mc_(form, 'D2. If this meant your order arrived 2-3 days faster, would you be more okay with it?',
      ['Yes, much more', 'A little more', 'No difference']);
  mc_(form, 'D3. Would you want to be told that your parcel came this way?',
      ['Yes, I would want to know', 'I do not mind either way', 'I would prefer not to know']);
  cb_(form, 'D4. What would worry you about it?', ['It might have been used or tried on', 'It might be damaged',
      'Hygiene', 'It might be old stock', 'Nothing would worry me']);

  // ---------- Section E
  form.addPageBreakItem().setTitle('Last few questions');
  mc_(form, 'E1. When you buy clothes online, how do you usually find them?', ['From bestseller or trending lists',
      'By searching for something specific', 'By scrolling through recommendations',
      'From links friends or family share on WhatsApp']);
  mc_(form, 'E2. Have you ever ordered exactly the same product as a friend, neighbour or relative?',
      ['Yes, several times', 'Yes, once', 'No', 'Not sure']);
  form.addTextItem().setTitle('E3. First 3 digits of your PIN code (optional)')
      .setHelpText('Only the first 3 digits, e.g. 208 for Kanpur. Used to group answers by district.')
      .setValidation(FormApp.createTextValidation().requireTextMatchesPattern('^[1-9][0-9]{2}$')
      .setHelpText('Please enter 3 digits').build()).setRequired(false);
  form.addParagraphTextItem().setTitle('E4. Anything else about online deliveries you would like to tell us?').setRequired(false);

  // ---------- Branching (set after the pages exist)
  a3.setChoices([
      a3.createChoice('Every week', FormApp.PageNavigationType.CONTINUE),
      a3.createChoice('A few times a month', FormApp.PageNavigationType.CONTINUE),
      a3.createChoice('About once a month', FormApp.PageNavigationType.CONTINUE),
      a3.createChoice('A few times a year', FormApp.PageNavigationType.CONTINUE),
      a3.createChoice('Rarely or never', FormApp.PageNavigationType.SUBMIT)]);
  b1.setChoices([
      b1.createChoice('Yes, I refused it at the door', FormApp.PageNavigationType.CONTINUE),
      b1.createChoice('Yes, I missed the delivery and it went back', FormApp.PageNavigationType.CONTINUE),
      b1.createChoice('Yes, both have happened', FormApp.PageNavigationType.CONTINUE),
      b1.createChoice('No', pageC)]);

  Logger.log('Customer survey EDIT link:  ' + form.getEditUrl());
  Logger.log('Customer survey SHARE link: ' + form.getPublishedUrl());
}
