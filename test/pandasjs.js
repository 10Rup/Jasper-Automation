Usually in JavaScript people use:

Native JS arrays
Danfo.js (similar to Pandas)
Lodash
SheetJS (xlsx) for Excel files
1. Sample Data
const data = [
  { name: "Rup", subject: "Math", marks: 90, fees: 1000 },
  { name: "Amit", subject: "Science", marks: 80, fees: 1200 },
  { name: "Rup", subject: "English", marks: 70, fees: 1100 },
  { name: "Neha", subject: "Math", marks: 95, fees: 1000 },
  { name: "Amit", subject: "English", marks: 85, fees: 1300 }
];
2. Add New Column
const result = data.map(row => ({
  ...row,
  bonus: 5
}));

console.log(result);
3. Sum
const total = data.reduce((sum, row) => {
  return sum + row.marks;
}, 0);

console.log(total);
4. Average / Mean
const avg =
  data.reduce((sum, row) => sum + row.marks, 0)
  / data.length;

console.log(avg);
5. Filter
Marks > 80
const filtered = data.filter(row => row.marks > 80);

console.log(filtered);
6. Multiple Filters
const filtered = data.filter(row =>
  row.marks > 80 &&
  row.fees >= 1000
);

console.log(filtered);
7. Group By

Native JS does not have direct groupby like Pandas.

You can do:

const grouped = data.reduce((acc, row) => {

  if (!acc[row.name]) {
    acc[row.name] = [];
  }

  acc[row.name].push(row);

  return acc;

}, {});

console.log(grouped);
8. Group By + Sum
const groupedSum = data.reduce((acc, row) => {

  if (!acc[row.name]) {
    acc[row.name] = 0;
  }

  acc[row.name] += row.marks;

  return acc;

}, {});

console.log(groupedSum);

Output:

{
  Rup: 160,
  Amit: 165,
  Neha: 95
}
9. Sort
const sorted = [...data].sort((a, b) => {
  return b.marks - a.marks;
});

console.log(sorted);
10. Find Max
const max = Math.max(
  ...data.map(x => x.marks)
);

console.log(max);
11. Find Min
const min = Math.min(
  ...data.map(x => x.marks)
);

console.log(min);
12. Count
console.log(data.length);
13. Unique Values
const unique = [...new Set(
  data.map(x => x.name)
)];

console.log(unique);
14. Map Values
const grades = {
  90: "A",
  80: "B"
};

const result = data.map(row => ({
  ...row,
  grade: grades[row.marks]
}));

console.log(result);
15. Create Conditional Column
const result = data.map(row => ({
  ...row,
  result: row.marks >= 80
    ? "Pass"
    : "Fail"
}));

console.log(result);
16. Merge Arrays (Like Pandas Merge)
const cityData = [
  { name: "Rup", city: "Mumbai" },
  { name: "Amit", city: "Delhi" }
];

const merged = data.map(row => {

  const city = cityData.find(
    x => x.name === row.name
  );

  return {
    ...row,
    city: city?.city
  };

});

console.log(merged);
17. Read Excel File in JS

Use SheetJS (xlsx)

Install:

npm install xlsx
Read Excel
const XLSX = require("xlsx");

const workbook = XLSX.readFile("students.xlsx");

const sheetName = workbook.SheetNames[0];

const sheet = workbook.Sheets[sheetName];

const data = XLSX.utils.sheet_to_json(sheet);

console.log(data);
18. Write Excel File
const XLSX = require("xlsx");

const worksheet = XLSX.utils.json_to_sheet(data);

const workbook = XLSX.utils.book_new();

XLSX.utils.book_append_sheet(
  workbook,
  worksheet,
  "Students"
);

XLSX.writeFile(workbook, "output.xlsx");
19. Use Danfo.js (Pandas Like Library)

Install:

npm install danfojs-node
Example
const dfd = require("danfojs-node");

const df = new dfd.DataFrame(data);

df.print();
Sum
df["marks"].sum();
Mean
df["marks"].mean();
GroupBy
df.groupby(["name"]).sum().print();
Difference Between Pandas and JS
Pandas	JavaScript
Easier for data analytics	More manual coding
Powerful groupby	Need reduce/map
Best for backend/data science	Best for frontend/web
Faster for data processing	Good for UI integration
Great for AI/report systems	Great for dashboards
For Your Dashboard Project

Since you are building:

dashboards
reports
Plotly graphs
Excel upload systems

Best approach:

Backend

Use:

Python
Pandas

for:

heavy processing
groupby
aggregations
AI query generation
Frontend

Use:

JavaScript
React
Plotly.js

for:

charts
filters
UI rendering
interactivity

This is the industry-standard architecture.