import unittest

from literature_agent import format_articles, parse_pubmed_xml

SAMPLE = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">12345678</PMID>
      <Article>
        <Journal>
          <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
          <Title>Nature Genetics</Title>
        </Journal>
        <ArticleTitle>Loss of <i>TP53</i> drives tumour growth</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">TP53 is a tumour suppressor.</AbstractText>
          <AbstractText Label="RESULTS">Knockout increased growth.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Smith</LastName><Initials>J</Initials></Author>
          <Author><CollectiveName>HackBio Consortium</CollectiveName></Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


class ParsePubmedXmlTest(unittest.TestCase):
    def test_parses_fields(self):
        [article] = parse_pubmed_xml(SAMPLE)
        self.assertEqual(article.pmid, "12345678")
        self.assertEqual(article.title, "Loss of TP53 drives tumour growth")
        self.assertEqual(article.journal, "Nature Genetics")
        self.assertEqual(article.year, "2024")
        self.assertEqual(article.authors, ["Smith J", "HackBio Consortium"])
        self.assertIn("BACKGROUND: TP53 is a tumour suppressor.", article.abstract)
        self.assertIn("RESULTS: Knockout increased growth.", article.abstract)

    def test_format_includes_pmid_tag(self):
        text = format_articles(parse_pubmed_xml(SAMPLE))
        self.assertIn('<article pmid="12345678">', text)


if __name__ == "__main__":
    unittest.main()
