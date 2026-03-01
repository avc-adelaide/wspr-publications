
AURORA_BIBFILE=aurora-journal-papers.bib
RMS_FILENAME=rms
EXT_DIR=external
REPORTS_DIR=reports

help:
	@echo "scholar - run Google Scholar report"
	@echo "install - install req'd packages"

scholar:
	uv run scripts/scholar_sync.py --user-id kxCnpPEAAAAJ --update-scholar-id

install:
	@echo "Installing poppler for pdftotext:"
	brew install poppler

doi: ${REPORTS_DIR}/${RMS_FILENAME}.txt
	egrep -o '10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+' ${REPORTS_DIR}/${RMS_FILENAME}.txt | sort -u > ${REPORTS_DIR}/doi-rms.txt
	egrep -o '10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+' ${EXT_DIR}/${AURORA_BIBFILE} | sort -u > ${REPORTS_DIR}/doi-aurora.txt

title: ${REPORTS_DIR}/${RMS_FILENAME}.txt
	tr -d '[:cntrl:]' < ${REPORTS_DIR}/${RMS_FILENAME}.txt \
	| sed -E 's/ ?\[[0-9]+\]/\n&/g' \
	| grep -Eo '‘[^’]+’' \
	| sed 's/[‘’]//g' \
	| sort -u \
	> ${REPORTS_DIR}/title-rms.txt
	sed -nE 's/.*title = \{(.*)\},/\1/p' ${EXT_DIR}/${AURORA_BIBFILE} | sort -u > ${REPORTS_DIR}/title-aurora.txt
	# echo "PAPERS in RMS but not in AURORA:"
	# comm -23 ${REPORTS_DIR}/title-rms.txt ${REPORTS_DIR}/title-aurora.txt
	# echo "PAPERS in AURORA but not in RMS:"
	# comm -13 ${REPORTS_DIR}/title-rms.txt ${REPORTS_DIR}/title-aurora.txt

${REPORTS_DIR}/${RMS_FILENAME}.txt:
	pdftotext ${EXT_DIR}/${RMS_FILENAME}.pdf ${REPORTS_DIR}/${RMS_FILENAME}.txt

${REPORTS_DIR}:
	makedir -p ${REPORTS_DIR}
