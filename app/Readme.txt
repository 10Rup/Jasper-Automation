This is the latest version of the jasper automation project



1. Uploading and converting pdf to image format, uploading jrxml files for correction purpose and reference purpose and storing then in local folder and this local path is saved in db as well.


2. We will show the uploaded file int he view page based on the purpose it was uploaded like for new report, correction or for reference purpose.


3. For new report generation
    a. We will use the upload pdf file that is converted to png file and process them in creating a new report.

    For html report design-
    ---- Before the process we can generate html report as well using the html generate button ---

    b. During the process inside the precess page, we will crop the image in different section and save them based on the band it has to be created.

    c. Set the report query in the view page if available(optional). Here we will add the query or can edit the queyr later if required and once qeury is uploaded we will use api to extact the columns from the query and store them in db.

    d. Once the image is cropped for the respective bands and query is set (optional), we will move on to next step that is report generating. 
    We can do it in 2 steps that is (1)Generating code one-by-one for the respective band and then saving them in db, once all the code is generated we well move to next step compile.(2)Or we can  generate the code in bulk just by pressing the generate code button at the right top, and once the code is generated its automatically prepare the report and move you to report download page.

    In the method-(1), after compile button is pressed it will compile all the code together and prepare the report then move you to report download page.


4. For correction purpose
    a. In correction purpose first thing is when you upload the jrxml report for correction process it will ask for the correction that have to be done, a image with the correction mention or marked (optional).

    b. Once the coreection details and image (optional) is shared during the upload you can view the file in view page under correction section.

    c. In correction section you can change the correction details and correction image as well.
    d. Once all details shared is true we can press the make correction button to start the correction process.
    
    e. Api will read the jrxml file, analyse the correction-image(optional) and use the correction details shared as prompt and generate a new report with the required corrections, ypu will be moved to report download page where you can download the new corrected report.

