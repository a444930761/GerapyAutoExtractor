import math
import operator
import re
from loguru import logger
import numpy as np
from collections import defaultdict

from gerapy_auto_extractor.utils.cluster import cluster_dict
from gerapy_auto_extractor.utils.element import similarity_with_siblings, number_of_linked_tag, linked_descendants, \
    text, siblings, descendants
from gerapy_auto_extractor.utils.preprocess import preprocess4list
from gerapy_auto_extractor.extractors.base import BaseExtractor
from gerapy_auto_extractor.utils.element import descendants_of_body, number_of_siblings, number_of_descendants, parent
from gerapy_auto_extractor.schemas.element import Element

LIST_MIN_NUMBER = 5
LIST_MIN_LENGTH = 8
LIST_MAX_LENGTH = 35
SIMILARITY_THRESHOLD = 0.8


class ListExtractor(BaseExtractor):
    """
    extract list from index page
    """
    
    def __init__(self, min_number=LIST_MIN_NUMBER, min_length=LIST_MIN_LENGTH, max_length=LIST_MAX_LENGTH,
                 similarity_threshold=SIMILARITY_THRESHOLD):
        """
        init list extractor
        """
        super(ListExtractor, self).__init__()
        self.min_number = min_number
        self.min_length = min_length
        self.max_length = max_length
        self.avg_length = (self.min_length + self.max_length) / 2
        self.similarity_threshold = similarity_threshold
    
    def _probability_of_title_with_length(self, length):
        """
        get the probability of title according to length
        import matplotlib.pyplot as plt
        x = np.asarray(range(5, 40))
        y = list_extractor.probability_of_title_with_length(x)
        plt.plot(x, y, 'g', label='m=0, sig=2')
        plt.show()
        :param length:
        :return:
        """
        sigma = 6
        return np.exp(-1 * ((length - self.avg_length) ** 2) / (2 * (sigma ** 2))) / (math.sqrt(2 * np.pi) * sigma)
    
    def _build_clusters(self, element):
        """
        build candidate clusters according to element
        :return:
        """
        descendants_tree = defaultdict(list)
        descendants = descendants_of_body(element)
        for descendant in descendants:
            # descendant.id = hash(descendant)
            descendant.number_of_siblings = number_of_siblings(descendant)
            # if one element does not have enough siblings, this is not a child of candidate element
            if descendant.number_of_siblings + 1 < self.min_number:
                continue
            
            if descendant.linked_descendants_group_text_min_length > self.max_length:
                continue
            
            if descendant.linked_descendants_group_text_max_length < self.min_length:
                continue
            
            descendant.similarity_with_siblings = similarity_with_siblings(descendant)
            if descendant.similarity_with_siblings < self.similarity_threshold:
                continue
            descendants_tree[descendant.parent_selector].append(descendant)
        descendants_tree = dict(descendants_tree)
        
        # cut tree, remove parent block
        selectors = sorted(list(descendants_tree.keys()))
        last_selector = None
        for selector in selectors[::-1]:
            # if later selector
            if last_selector and selector and last_selector.startswith(selector):
                del descendants_tree[selector]
            last_selector = selector
        clusters = cluster_dict(descendants_tree)
        return clusters
    
    def _choose_best_cluster(self, clusters):
        """
        use clustering algorithm to choose best cluster from candidate clusters
        :param clusters:
        :return:
        """
        # choose best cluster using score
        clusters_score = defaultdict(dict)
        clusters_score_arg_max = 0
        clusters_score_max = -1
        for cluster_id, cluster in clusters.items():
            clusters_score[cluster_id]['avg_similarity_with_siblings'] = np.mean(
                [element.similarity_with_siblings for element in cluster])
            # TODO: add more quota to select best cluster
            clusters_score[cluster_id]['clusters_score'] = clusters_score[cluster_id]['avg_similarity_with_siblings']
            if clusters_score[cluster_id]['clusters_score'] > clusters_score_max:
                clusters_score_max = clusters_score[cluster_id]['clusters_score']
                clusters_score_arg_max = cluster_id
        best_cluster = clusters[clusters_score_arg_max]
        return best_cluster
    
    def _extract_from_cluster(self, cluster):
        """
        extract title and href from best cluster
        :param cluster:
        :return:
        """
        # get best tag path of title
        probabilities_of_title = defaultdict(list)
        for element in cluster:
            descendants = element.linked_descendants
            for descendant in descendants:
                _tag_path = descendant.tag_path
                descendant_text = text(descendant)
                probability_of_title_with_length = self._probability_of_title_with_length(len(descendant_text))
                # probability_of_title_with_descendants = self.probability_of_title_with_descendants(descendant)
                # TODO: add more quota to calculate probability_of_title
                probability_of_title = probability_of_title_with_length
                probabilities_of_title[_tag_path].append(probability_of_title)
        # get most probable tag_path
        probabilities_of_title_avg = {k: np.mean(v) for k, v in probabilities_of_title.items()}
        best_tag_path = max(probabilities_of_title_avg.items(), key=operator.itemgetter(1))[0]
        logger.debug(f'best tag path {best_tag_path}')
        
        # extract according to best tag path
        result = []
        for element in cluster:
            descendants = element.linked_descendants
            for descendant in descendants:
                _tag_path = descendant.tag_path
                if _tag_path != best_tag_path:
                    continue
                title = text(descendant)
                href = descendant.attrib.get('href')
                if not href:
                    continue
                result.append({
                    'title': title,
                    'href': href
                })
        return result
    
    def process(self, element: Element):
        """
        extract content from html
        :param element:
        :return:
        """
        # preprocess
        preprocess4list(element)
        
        # build clusters
        clusters = self._build_clusters(element)
        
        # choose best cluster
        best_cluster = self._choose_best_cluster(clusters)
        
        # extract result from best cluster
        return self._extract_from_cluster(best_cluster)


list_extractor = ListExtractor()


def extract_list(html):
    """
    extract list from index html
    :return:
    """
    return list_extractor.extract(html)


if __name__ == '__main__':
    import matplotlib.pyplot as plt
    
    x = np.asarray(range(0, 40))
    print('x', x)
    print(list_extractor.probability_of_title_with_length(17))
    y1 = list_extractor.probability_of_title_with_length(x)
    plt.plot(x, y1, 'g', label='m=0,sig=2')
    plt.show()
    print(list_extractor.probability_of_title_with_length(0))
