const fs = require('fs');

const data = JSON.parse(fs.readFileSync('data.json', 'utf8'));

// Define headers
const headers = ['name', 'location', 'suburb', 'spectrum', 'price', 'atmosphere', 'desc', 'oneLiner', 'tags', 'image', 'rating', 'reviews'];

// Convert arrays to pipe-separated strings and wrap text in quotes
const escapeCSV = (val) => {
    if (val === null || val === undefined) return '';
    if (Array.isArray(val)) {
        val = val.join('|');
    }
    const str = String(val);
    if (str.includes(',') || str.includes('\n') || str.includes('"')) {
        return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
};

const rows = data.map(shop => {
    return headers.map(header => escapeCSV(shop[header])).join(',');
});

const csvStr = headers.join(',') + '\n' + rows.join('\n');
fs.writeFileSync('data.csv', csvStr);
console.log('Successfully created data.csv');
