Create Sample DataFrame
import pandas as pd

data = {
    "Name": ["Rup", "Amit", "Rup", "Neha", "Amit"],
    "Subject": ["Math", "Science", "English", "Math", "English"],
    "Marks": [90, 80, 70, 95, 85],
    "Fees": [1000, 1200, 1100, 1000, 1300]
}

df = pd.DataFrame(data)

print(df)

Output:

   Name  Subject  Marks  Fees
0   Rup     Math     90  1000
1  Amit  Science     80  1200
2   Rup  English     70  1100
3  Neha     Math     95  1000
4  Amit  English     85  1300
1. Add New Column
df["Bonus"] = 5

print(df)
2. Add Two Columns
df["Total"] = df["Marks"] + df["Bonus"]

print(df)
3. Sum
total_marks = df["Marks"].sum()

print(total_marks)
4. Mean / Average

Both are same.

average_marks = df["Marks"].mean()

print(average_marks)
5. Group By
grouped = df.groupby("Name")

print(grouped)
6. Group By + Sum
result = df.groupby("Name")["Marks"].sum()

print(result)

Output:

Name
Amit    165
Neha     95
Rup     160
7. Group By + Mean
result = df.groupby("Name")["Marks"].mean()

print(result)
8. Group By Multiple Columns
result = df.groupby(["Name", "Subject"])["Marks"].sum()

print(result)
9. Filter Rows
Marks greater than 80
filtered = df[df["Marks"] > 80]

print(filtered)
10. Multiple Filters
filtered = df[
    (df["Marks"] > 80) &
    (df["Fees"] >= 1000)
]

print(filtered)
11. agg() Function

Use multiple operations together.

result = df.groupby("Name").agg({
    "Marks": ["sum", "mean", "max"],
    "Fees": ["sum", "mean"]
})

print(result)
12. Max Value
print(df["Marks"].max())
13. Min Value
print(df["Marks"].min())
14. Count
print(df["Marks"].count())
15. Unique Values
print(df["Name"].unique())
16. Value Counts
print(df["Name"].value_counts())
17. Sort Values
sorted_df = df.sort_values(by="Marks", ascending=False)

print(sorted_df)
18. Rename Column
df.rename(columns={
    "Marks": "StudentMarks"
}, inplace=True)

print(df)
19. Drop Column
df.drop(columns=["Fees"], inplace=True)

print(df)
20. Select Columns
print(df[["Name", "Marks"]])
21. Create Conditional Column
df["Result"] = df["Marks"].apply(
    lambda x: "Pass" if x >= 80 else "Fail"
)

print(df)
22. Fill Missing Values
df.fillna(0, inplace=True)
23. Remove Null Rows
df.dropna(inplace=True)
24. Merge DataFrames
df2 = pd.DataFrame({
    "Name": ["Rup", "Amit"],
    "City": ["Mumbai", "Delhi"]
})

merged = pd.merge(df, df2, on="Name")

print(merged)
25. Pivot Table
pivot = df.pivot_table(
    values="Marks",
    index="Name",
    aggfunc="sum"
)

print(pivot)
26. Head
print(df.head())
27. Tail
print(df.tail())
28. Shape
print(df.shape)
29. Columns List
print(df.columns)
30. Data Types
print(df.dtypes)
31. Describe Statistics
print(df.describe())
32. Duplicate Rows
print(df.duplicated())
33. Remove Duplicates
df.drop_duplicates(inplace=True)
34. Query Method
result = df.query("Marks > 80")

print(result)
35. isin()
result = df[df["Name"].isin(["Rup", "Neha"])]

print(result)
36. String Operations
df["Name"] = df["Name"].str.upper()

print(df)
37. Convert Column Type
df["Marks"] = df["Marks"].astype(float)
38. Apply Function
df["DoubleMarks"] = df["Marks"].apply(
    lambda x: x * 2
)

print(df)
39. Map Values
grade_map = {
    90: "A",
    80: "B"
}

df["Grade"] = df["Marks"].map(grade_map)

print(df)
40. Iterating Rows
for index, row in df.iterrows():
    print(row["Name"], row["Marks"])
Most Commonly Used in Real Projects

You will use these the most:

read_excel()
groupby()
agg()
merge()
filter
sum()
mean()
apply()
pivot_table()
to_dict()
sort_values()