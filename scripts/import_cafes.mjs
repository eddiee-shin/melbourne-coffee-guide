#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const args = parseArgs(process.argv.slice(2));
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = args.root ? path.resolve(args.root) : path.resolve(scriptDir, '..');
const defaultInput = path.join(repoRoot, 'data.json');
const inputPath = path.resolve(args.input || defaultInput);
const mode = (args.mode || 'dry-run').toLowerCase();
const table = args.table || 'cafes';
const batchSize = Number(args.batchSize || 100);
const outputPath = args.output ? path.resolve(args.output) : null;
const supabaseUrl = args.supabaseUrl || process.env.SUPABASE_URL;
const supabaseKey = args.supabaseKey || process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY;

const raw = await fs.readFile(inputPath, 'utf8');
const source = JSON.parse(raw);
if (!Array.isArray(source)) {
  throw new Error(`Expected ${inputPath} to contain a JSON array.`);
}

const cafes = source.map(normalizeCafe);
const duplicates = findDuplicates(cafes.map(c => c.slug));

if (duplicates.length) {
  console.error(`Warning: duplicate slugs found: ${duplicates.join(', ')}`);
}

if (mode === 'dry-run') {
  console.log(JSON.stringify({
    input: inputPath,
    rows: cafes.length,
    unique_slugs: new Set(cafes.map(c => c.slug)).size,
    sample: cafes.slice(0, Math.min(3, cafes.length)),
  }, null, 2));
  process.exit(0);
}

if (mode === 'csv') {
  const csv = toCsv(cafes);
  if (outputPath) {
    await fs.writeFile(outputPath, csv, 'utf8');
    console.log(`Wrote ${cafes.length} cafe rows to ${outputPath}`);
  } else {
    process.stdout.write(csv);
  }
  process.exit(0);
}

if (mode === 'sql') {
  const sql = toSqlUpserts(cafes, table);
  if (outputPath) {
    await fs.writeFile(outputPath, sql, 'utf8');
    console.log(`Wrote SQL upsert script for ${cafes.length} cafe rows to ${outputPath}`);
  } else {
    process.stdout.write(sql);
  }
  process.exit(0);
}

if (mode === 'rest') {
  if (!supabaseUrl || !supabaseKey) {
    throw new Error('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) are required for REST mode.');
  }

  const endpoint = `${trimSlash(supabaseUrl)}/rest/v1/${table}?on_conflict=slug`;
  const totalBatches = Math.ceil(cafes.length / batchSize);

  for (let i = 0; i < cafes.length; i += batchSize) {
    const batch = cafes.slice(i, i + batchSize);
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        apikey: supabaseKey,
        authorization: `Bearer ${supabaseKey}`,
        'content-type': 'application/json',
        prefer: 'resolution=merge-duplicates,return=minimal',
      },
      body: JSON.stringify(batch),
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Supabase REST import failed for batch ${Math.floor(i / batchSize) + 1}/${totalBatches}: ${res.status} ${res.statusText}\n${body}`);
    }

    console.log(`Imported batch ${Math.floor(i / batchSize) + 1}/${totalBatches} (${batch.length} rows)`);
  }

  console.log(`Done. Upserted ${cafes.length} cafe rows into ${table}.`);
  process.exit(0);
}

throw new Error(`Unknown mode: ${mode}. Use dry-run, csv, sql, or rest.`);

function normalizeCafe(row) {
  const oneLiner = row.one_liner ?? row.oneLiner ?? '';
  return {
    slug: slugify(row.name),
    name: requiredText(row.name, 'name'),
    location: requiredText(row.location, 'location'),
    suburb: requiredText(row.suburb, 'suburb'),
    active: row.active === undefined ? true : Boolean(row.active),
    spectrum: toNumber(row.spectrum, 'spectrum'),
    price: toInteger(row.price, 'price'),
    atmosphere: requiredText(row.atmosphere, 'atmosphere'),
    description: requiredText(row.desc ?? row.description, 'desc'),
    one_liner: requiredText(oneLiner, 'oneLiner'),
    tags: requiredText(row.tags, 'tags'),
    image: optionalText(row.image),
    image_url: optionalText(row.image_url),
    image_path: optionalText(row.image_path),
    rating: toNumber(row.rating, 'rating'),
    reviews: toInteger(row.reviews, 'reviews'),
    lat: optionalNumber(row.lat),
    lng: optionalNumber(row.lng),
    signature: optionalText(row.signature),
    last_scraped_at: optionalText(row.last_scraped_at),
  };
}

function toCsv(rows) {
  const headers = [
    'slug', 'name', 'location', 'suburb', 'active', 'spectrum', 'price', 'atmosphere', 'description',
    'one_liner', 'tags', 'image', 'image_url', 'image_path', 'rating', 'reviews', 'lat', 'lng', 'signature', 'last_scraped_at'
  ];
  const lines = [headers.join(',')];
  for (const row of rows) {
    lines.push(headers.map(h => csvCell(row[h])).join(','));
  }
  return `${lines.join('\n')}\n`;
}

function toSqlUpserts(rows, tableName) {
  const sqlRows = rows.map(row => `(${[
    sqlString(row.slug),
    sqlString(row.name),
    sqlString(row.location),
    sqlString(row.suburb),
    sqlBoolean(row.active ?? true),
    sqlNumber(row.spectrum),
    sqlNumber(row.price),
    sqlString(row.atmosphere),
    sqlString(row.description),
    sqlString(row.one_liner),
    sqlString(row.tags),
    sqlStringOrNull(row.image),
    sqlStringOrNull(row.image_url),
    sqlStringOrNull(row.image_path),
    sqlNumber(row.rating),
    sqlNumber(row.reviews),
    sqlNumberOrNull(row.lat),
    sqlNumberOrNull(row.lng),
    sqlStringOrNull(row.signature),
    sqlStringOrNull(row.last_scraped_at),
  ].join(', ')})`).join(',\n');

  return `insert into public.${tableName} (
  slug, name, location, suburb, active, spectrum, price, atmosphere, description, one_liner, tags, image, image_url, image_path, rating, reviews, lat, lng, signature, last_scraped_at
) values
${sqlRows}
on conflict (slug) do update set
  name = excluded.name,
  location = excluded.location,
  suburb = excluded.suburb,
  spectrum = excluded.spectrum,
  price = excluded.price,
  atmosphere = excluded.atmosphere,
  description = excluded.description,
  one_liner = excluded.one_liner,
  tags = excluded.tags,
  image = excluded.image,
  rating = excluded.rating,
  reviews = excluded.reviews,
  lat = excluded.lat,
  lng = excluded.lng,
  signature = excluded.signature,
  updated_at = timezone('utc', now());
`;
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith('--')) continue;
    const key = arg.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) {
      out[key] = true;
    } else {
      out[key] = next;
      i++;
    }
  }
  return out;
}

function slugify(value) {
  return String(value)
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, '-');
}

function requiredText(value, field) {
  const text = optionalText(value);
  if (!text) throw new Error(`Missing required field: ${field}`);
  return text;
}

function optionalText(value) {
  if (value === undefined || value === null) return null;
  const text = String(value).trim();
  return text.length ? text : null;
}

function toNumber(value, field) {
  const num = Number(value);
  if (!Number.isFinite(num)) throw new Error(`Invalid numeric value for ${field}: ${value}`);
  return num;
}

function optionalNumber(value) {
  if (value === undefined || value === null || value === '') return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function toInteger(value, field) {
  const num = Number(value);
  if (!Number.isFinite(num)) throw new Error(`Invalid integer value for ${field}: ${value}`);
  return Math.trunc(num);
}

function csvCell(value) {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (/[",\n]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

function sqlString(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function sqlBoolean(value) {
  return value ? 'true' : 'false';
}

function sqlStringOrNull(value) {
  return value === null || value === undefined ? 'null' : sqlString(value);
}

function sqlNumber(value) {
  return Number.isFinite(value) ? String(value) : 'null';
}

function sqlNumberOrNull(value) {
  return value === null || value === undefined ? 'null' : sqlNumber(value);
}

function findDuplicates(values) {
  const seen = new Set();
  const duplicates = new Set();
  for (const value of values) {
    if (seen.has(value)) duplicates.add(value);
    seen.add(value);
  }
  return [...duplicates];
}

function trimSlash(value) {
  return String(value).replace(/\/$/, '');
}
