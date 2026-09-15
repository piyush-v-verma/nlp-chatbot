import nltk

def get_chunks(pos_tags):
    """Constructs NP/VP chunk parsing using NLTK RegexpParser, returns nested JSON structure."""
    if not pos_tags:
        return {"label": "S", "children": []}
        
    grammar = r"""
      NP: {<DT>?<JJ>*<NN.?>+}   # Noun Phrase
      VP: {<MD>?<VB.?>+<NP|PP>*} # Verb Phrase
      PP: {<IN><NP>}             # Prepositional Phrase
    """
    try:
        cp = nltk.RegexpParser(grammar)
        tree = cp.parse(pos_tags)
        return _tree_to_json(tree)
    except Exception as e:
        print(f"Chunking error: {e}")
        return {
            "label": "S",
            "children": [{"word": word, "tag": tag} for word, tag in pos_tags]
        }

def _tree_to_json(tree):
    """Converts NLTK Tree structure to a serializable nested dict."""
    if isinstance(tree, nltk.Tree):
        return {
            "label": tree.label(),
            "children": [_tree_to_json(child) for child in tree]
        }
    else:
        return {
            "word": tree[0],
            "tag": tree[1]
        }
