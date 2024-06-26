import os
import numpy as np
import pandas as pd
import pingouin as pg
import matplotlib.pyplot as plt
import scipy.stats as sps
import statsmodels.stats.multitest as smsm
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from tqdm import trange
import seaborn as sns
import matplotlib.colors as mcolors

# 整理数据，方便后续计算
# 输入原始数据（.csv文件，包括表型信息和体积指标，meta+data），得到patients.csv和controls.csv两个文件，其中只包含个体编号、协变量、脑区体积信息等后续要用的；
# group_index：输入文件中，区分疾病和健康的一列的index；group_name：2个元素的列表，第一个为ctrl的名称（小鼠用'WT'），第二个为patient的名称（小鼠用'MUT'）。
# cova_name: list，年龄、性别等协变量的column names；
# region_name: list，脑区名称的column names；
# 输出完成筛选和分类的数据。指定tp='0'，输出对照组和疾病组两个.csv文件。放在同一outpath，后续可以自动识别和计算IDSCN。
def generate_dataset(filepath, outpath, group_name, group_index, cova_name, region_name=None, tp='0'):
    """
    This method will generate the control group and standard patient data (covariates in front
    and regions behind) from raw data.

    |<--                  raw data                     -->|                   |<--cova-->|   |<--    regions   -->|
    subject    name    age    sex    region1    region2 ...         subject    age    sex    region1    region2 ...
    sub-001    Amy     18     Female (number)   (number)     --->   sub-001    18     Female (number)   (number)
    sub-002    Bob     20     Male   (number)   (number)            sub-002    20     Male   (number)   (number)
    sub-003    Chris   30     Female (number)   (number)            sub-003    30     Female (number)   (number)

    :param filepath: str
           path of raw data file. The source file is .csv type.
    :param outpath: str
           path to the generated files.
    :param group_name: string or list
           group name of control group data or patient.
           if tp == 0, params must be a list with two elements, the first element (list or string)
           is for control group and the second (list or string) is for patients.
           if tp != 0, params is a list or string.
    :param group_index: integer
           index of column to separate control group data and patient data.
    :param cova_name: list
           name list of covariates.
    :param region_name: list
           name list of regions.
    :param tp: integer
           type of generate mode.
           0 -> generate both control group and patient data.
           1 -> only generate control group.
           2 -> only generate patient data.
    :return:
    """

    # check the parameters
    assert isinstance(filepath, str), 'filepath must be a string.'
    assert filepath.strip().split('.')[-1] == 'csv', 'input file must be a .csv file.'
    assert os.path.exists(filepath), 'input file is not exist.'
    assert isinstance(outpath, str), 'outpath must be a string.'
    assert isinstance(cova_name, list), 'cova_name must be a list.'
    for cova in cova_name:
        assert isinstance(cova, str), 'items in cova_name must be string.'
    assert region_name is None or isinstance(region_name, list), 'region_name must be a list.'
    if region_name is not None:
        for region in region_name:
            assert isinstance(region, str), 'items in region_name must be string.'
    assert isinstance(group_name, str) or isinstance(group_name, list), 'params must be a string or list.'
    assert tp in ['0', '1', '2'], 'tp must be an integer, which is 0, 1 or 2.'
    if tp == '0':
        assert len(group_name) == 2, 'length of params must be less than two with tp==0.'
        for group in group_name:
            if isinstance(group, list):
                for g in group:
                    assert isinstance(g, str), 'group name of control case and patient must be string.'
            elif isinstance(group, str):
                pass
            else:
                raise TypeError('group name of control case or patient must be string.')
    else:
        if isinstance(group_name, list):
            for group in group_name:
                assert isinstance(group, str), 'group name of control case and patient must be string.'
    assert isinstance(group_index, int) and group_index > 0, 'group index must be an integer and greater than 0.'

    # start generate
    outPath = outpath
    if outpath[-1] in ['/', '\\']:
        outPath = outpath[:-1]
    if not os.path.exists(outPath) or os.path.isfile(outPath):
        os.makedirs(outPath)
    print('Raw data path is: {}'.format(filepath))
    print('Outpath is: {}'.format(outpath))

    raw = pd.read_csv(filepath, encoding_errors='ignore')
    source = raw[[raw.columns.values[group_index - 1], raw.columns.values[0]] + cova_name + region_name]
    col_group = source.columns.values[0]
    source = source.dropna(axis=0)
    for cvn in cova_name:
        if source[cvn].dtype == 'object':
            factors = set(list(source[cvn].values))
            for j, f in zip(range(len(factors)), factors):
                source[cvn] = source[cvn].replace(f, j + 1)
    if tp == '0':
        hc = (source.loc[source[col_group].isin(group_name[0])])[source.columns.values[1:]]
        pa = (source.loc[source[col_group].isin(group_name[1])])[source.columns.values[1:]]
        hc.to_csv(outPath + '/controls.csv', index=False)
        print('Generate {} successfully!'.format(outPath + '/controls.csv'))
        pa.to_csv(outPath + '/patients.csv', index=False)
        print('Generate {} successfully!'.format(outPath + '/patients.csv'))
    elif tp == '1':
        hc = (source.loc[source[col_group].isin(group_name)])[source.columns.values[1:]]
        hc.to_csv(outPath + '/controls.csv', index=False)
        print('Generate {} successfully!'.format(outPath + '/controls.csv'))
    else:
        pa = (source.loc[source[col_group].isin(group_name)])[source.columns.values[1:]]
        pa.to_csv(outPath + '/patients.csv', index=False)
        print('Generate {} successfully!'.format(outPath + '/patients.csv'))
    print('Dataset is generated successfully!')


def read_dataset(filepath, tp, cova, region):
    """
    This method will read the generated dataset of controls or patients.

    :param filepath: str
           path of raw data file. The source file is .csv type.
    :param tp: str
           data type of the dataset, controls or patients,so it must be in ['ctrl','pati'].
    :param c_r: tuple
           total covariates and regions.
           e.g. (2,3) expresses 2 covariates and 3 regions.
    :param cova: list
           name list of selected covariates.
    :param region: list
           name list of selected regions.

    :return: (cova_cols, region_cols, ct) or (pati_subs, cova_cols, region_cols, pa)
    """

    # check the parameters
    assert isinstance(filepath, str), 'filepath must be a string.'
    assert filepath.strip().split('.')[-1] == 'csv', 'input file must be a .csv file.'
    assert os.path.exists(filepath), 'input file is not exist.'
    assert tp in ['ctrl', 'pati'], 'tp must be "ctrl" or "pati".'
    assert isinstance(cova, list), 'cova must be a list.'
    for c in cova:
        assert isinstance(c, str), 'items in cova_name must be string.'
    assert isinstance(region, list), 'region must be a list.'
    for r in region:
        assert isinstance(r, str), 'items in region must be string.'

    # start run
    df = pd.read_csv(filepath, encoding='utf-8', encoding_errors='ignore')
    covas = df[cova]
    regions = df[region]
    if tp == 'ctrl':
        ctrl_covas = covas
        ctrl_regions = regions
        ct = pd.concat([ctrl_covas, ctrl_regions], axis=1)
        return list(ctrl_covas.columns.values), list(ctrl_regions.columns.values), ct
    else:
        pati_subs = list(df.iloc[:, 0].values)
        pa = pd.concat([covas, regions], axis=1)
        return list(pati_subs), list(covas.columns.values), list(regions.columns.values), pa

# input: covar names, region names, data;
# output: partial correlation matrix (i.e. PCCn)
def PCC(covas, regions, group):
    """
    This method will generate the partial correlation matrix (i.e. PCCn).

    :param covas: list
           name list of covariates.
    :param regions: list
           name list of regions.
    :param group: pandas.core.frame.DataFrame
           group data.

    :return: PCC
    """

    assert isinstance(covas, list), 'covas must be a list.'
    for cova in covas:
        assert isinstance(cova, str), 'items in covas must be string.'
    assert isinstance(regions, list), 'regions must be a list.'
    for region in regions:
        assert isinstance(region, str), 'items in covas must be string.'
    assert isinstance(group, pd.DataFrame), 'ctrl_group must be a pandas.core.frame.DataFrame.'

    # calculate partial_corr
    pcorr = []
    for r1 in regions:
        pcorr_col = []
        for r2 in regions:
            if r1 != r2:
                results = pg.partial_corr(data=group, x=r1, y=r2, covar=covas)
                pcorr_col.append(results.r.values[0])
            else:
                pcorr_col.append(1.0)
        pcorr.append(pcorr_col)
    return np.array(pcorr).astype(np.float_)


def mix_group(cols, ctrl, pati):
    """
    This method will mix a patient into the control group and return mixed group.

    :param cols:list
           name list of ctrl DataFrame columns.
    :param ctrl:pandas.core.frame.DataFrame
           control group data.
    :param pati:numpy.ndarray
           patient data.
    :return: mixed
    """
    prow = np.array([list(pati)])
    pati = pd.DataFrame(prow, columns=cols)
    mixed = pd.concat([ctrl, pati])
    return mixed


def Z_score(PCCn, delta_PCC):
    """
    This method is to calculate Z-score.

    :param PCCn:
    :param delta_PCC:
    :return: Z
    """

    assert isinstance(PCCn, np.ndarray), 'PCCn must be a numpy.ndarray.'
    assert isinstance(delta_PCC, np.ndarray), 'delta_PCC must be a numpy.ndarray.'
    assert PCCn.shape == delta_PCC.shape, 'shape of PCCn and delta_PCC must be equal.'

    n = PCCn.shape[0]
    ones = np.ones(PCCn.shape, dtype=np.float_)
    d = ones - PCCn * PCCn
    for i in range(n):
        d[i][i] = 1
    Z = (n - 1) * delta_PCC / d
    for i in range(n):
        Z[i][i] = 1
    return Z


def IDSCN(inpath, outpath, cova=None, region=None):
    if os.path.isdir(outpath):
        l = os.listdir(outpath)
        if len(l) != 0:
            print('Please input a empty directory for outpath!')
            exit(1)
    outPath = outpath
    if outpath[-1] in ['/', '\\']:
        outPath = outpath[:-1]
    if not os.path.exists(outPath) or os.path.isfile(outPath):
        os.makedirs(outPath)
    ctrl_path = os.path.normpath(os.path.join(inpath, 'controls.csv')) #规范路径，在Windows系统上将/替换为\
    pati_path = os.path.normpath(os.path.join(inpath, 'patients.csv'))
    print('Controls are in {}'.format(ctrl_path))
    print('Patients are in {}'.format(pati_path))
    ctrl = read_dataset(filepath=ctrl_path, tp='ctrl', cova=cova, region=region)
    pati = read_dataset(filepath=pati_path, tp='pati', cova=cova, region=region)
    df = pd.DataFrame(columns=ctrl[1], index=ctrl[1])
    PCCn = PCC(covas=ctrl[0], regions=ctrl[1], group=ctrl[2])
    df.iloc[:, :] = PCCn.T
    df.to_csv(outPath + '/PCCn.csv')
    print('PCCn done.')
    # np.savetxt(outPath + '/PCCn.csv', PCCn, delimiter=',')
    np.savetxt(outPath + '/covas.txt', np.array(ctrl[0]), delimiter=',', fmt='%s')
    np.savetxt(outPath + '/regions.txt', np.array(ctrl[1]), delimiter=',', fmt='%s')
    pa = pati[3].values
    df_n = pd.DataFrame(columns=['subject', 'n'])
    for sub, p in zip(pati[0], pa):
        mixed_group = mix_group(ctrl[0] + ctrl[1], ctrl[2], p)
        PCCn_1 = PCC(ctrl[0], ctrl[1], mixed_group)
        delta_PCC = PCCn_1 - PCCn
        Z = Z_score(PCCn, delta_PCC)
        ori_P, correct_P = P(Z)
        if not os.path.exists(outPath + '/' + sub):
            os.mkdir(outPath + '/' + sub)
        df.iloc[:, :] = PCCn_1.T
        df.to_csv(outPath + '/' + sub + '/' + sub + '_PCCn+1.csv')
        df.iloc[:, :] = Z.T
        df.to_csv(outPath + '/' + sub + '/' + sub + '_Z.csv')
        df.iloc[:, :] = ori_P.T
        df.to_csv(outPath + '/' + sub + '/' + sub + '_P.csv')
        df.iloc[:, :] = correct_P.T
        df.to_csv(outPath + '/' + sub + '/' + sub + '_P_FDR.csv')
        df.loc[len(df.index)] = [sub, np.count_nonzero(correct_P < 0.05)]
        # np.savetxt(outPath + '/' + sub + '/' + sub + '_PCCn+1.csv', PCCn_1, delimiter=',')
        # np.savetxt(outPath + '/' + sub + '/' + sub + '_Z.csv', Z, delimiter=',')
        print('Subject: ', sub, ' done.')
    df_n.to_csv(outPath + '/count_significant.csv', index=False)
    print("All subjects' PCC are generated successfully!")


def read_matrix(path, tp):
    assert tp in ['pcc', 'z', 'sg'], 'tp must be in ["pcc", "z", "sg"]'
    dtype = np.int_
    if tp in ['pcc', 'z']:
        dtype = np.float_
    m = pd.read_csv(path, index_col=0).astype(dtype)
    return m.values


def P(Z):
    p = sps.norm.sf(abs(Z)) * 2
    shape = p.shape
    correct_P = smsm.fdrcorrection(p.flatten())
    return p, correct_P[1].reshape(shape)


def draw_signifcant(savepath, count, re_col, plot):
    index_dict = {}
    for i in range(count.shape[0]):
        for j in range(i + 1):
            if count[i][j] in index_dict.keys():
                index_dict[count[i][j]][0] += 1
                index_dict[count[i][j]][1].append((i, j))
            else:
                index_dict[count[i][j]] = [1, [(i, j)]]
    index_tuple = sorted(zip(index_dict.keys(), index_dict.values()), reverse=True)
    if plot:
        name_list = []
        y = []
        for c, locs in index_tuple:
            for loc in locs[1]:
                if c != 0:
                    name_list.append(re_col[loc[0]] + '--' + re_col[loc[1]])
                    y.append(c)
        view_len = int(len(name_list) * 0.1)
        if view_len > 200:
            view_len = 200
        name_list = name_list[:view_len]
        y = y[:len(name_list)]
        plt.figure(figsize=(100, 15))
        plt.bar(range(len(name_list)), y, tick_label=name_list)
        for name, num in zip(range(len(name_list)), y):
            plt.text(name, num, '%d' % num, ha='center')
        plt.title('Sorted Effective Connections')
        plt.xticks(fontsize=14, rotation=315, ha='left')
        plt.yticks(fontsize=20)
        plt.xlabel('Connection', fontsize=20)
        plt.ylabel('Number of significant people', fontsize=20)
        plt.tight_layout()
        plt.savefig(savepath)
        plt.show()
    return index_tuple


def getTopLocs(count, num):
    i = 0
    c = 0
    locs = []
    while c < num:
        c += count[i][1][0]
        locs += count[i][1][1]
        i += 1
    return locs


def subtype(input_dir, outpath, plot=True):
    assert isinstance(input_dir, str), 'input dir must be a string.'
    inputdir = input_dir
    if input_dir[-1] in ['/', '\\']:
        inputdir = input_dir[:-1]
    dirlist = os.listdir(inputdir)
    assert 'regions.txt' in dirlist, 'regions.txt not found.'
    f_re = open(inputdir + '/regions.txt', 'r')
    regions = [line.strip() for line in f_re.readlines()]
    pati = []
    for f in dirlist:
        if os.path.isdir(inputdir + '/' + f):
            pati.append(f)
    significant = None
    for p in pati:
        Z = read_matrix(inputdir + '/' + p + '/' + p + '_Z.csv', tp='z')
        if significant is None:
            significant = np.zeros(Z.shape)
        _, correct_P = P(Z)
        signi_conn_index = np.argwhere(correct_P < 0.05)
        if signi_conn_index.shape[0] > 0:
            rows, cols = zip(*signi_conn_index)
            significant[rows, cols] = significant[rows, cols] + 1
    sorted_edges = draw_signifcant(inputdir + '/' + inputdir.strip().split('/')[-1] + '.jpg', significant, regions,
                                   plot)
    sg_num = []
    for se in sorted_edges:
        sg_num.append(str(int(se[0])) + '/' + str(se[1][0]))
    print('Significant_count/Edge_num:')
    print(sg_num)
    select_num = int(input('Please input number of selected edges: '))
    selected_edges = getTopLocs(sorted_edges, select_num)
    print('Selected {} edges'.format(len(selected_edges)))

    row, col = zip(*selected_edges)
    cluster_source = []
    for p in pati:
        PCCn_1 = read_matrix(inputdir + '/' + p + '/' + p + '_PCCn+1.csv', tp='pcc')
        if PCCn_1 is not None:
            dist = np.ones((len(selected_edges),)) - PCCn_1[row, col]
            cluster_source.append(dist)
    cluster_source = np.array(cluster_source)
    dist_pred = None
    max_sc = -2
    k_last = 1

    for k in range(2, 6):
        dist_pred_k = KMeans(n_clusters=k, n_init=100).fit_predict(cluster_source.copy())
        sc = silhouette_score(cluster_source.copy(), dist_pred_k)
        if sc > max_sc:
            max_sc = sc
            dist_pred = dist_pred_k
            k_last = k
    clusters = [[] for i in range(k_last)]

    for p, c in zip(pati, dist_pred):
        clusters[c].append(p)
    ret = k_last, clusters, len(selected_edges), max_sc
    c_num = []
    df = pd.DataFrame(data={0: ret[1][0]}, columns=[0])
    c_num.append(str(len(ret[1][0])))
    for i in range(ret[0] - 1):
        tp = pd.DataFrame(data=ret[1][i + 1], columns=[i + 1])
        df = pd.concat([df, tp], axis=1, join='outer')
        c_num.append(str(len(ret[1][i + 1])))
    if not os.path.exists(outpath) or os.path.isfile(outpath):
        os.makedirs(outpath)
    outpath = os.path.normpath(os.path.join(outpath, 'cluster_result.csv'))
    df.to_csv(outpath, index=False)
    with open(outpath, mode='a+') as ff:
        print('Number of connections to cluster: ' + str(ret[2]))
        ff.write('Number of connections to cluster,' + str(ret[2]) + '\n')
        print('Number of cluster: ' + str(ret[0]))
        ff.write('Number of cluster,' + str(ret[0]) + '\n')
        print('Clustering result: ' + '/'.join(c_num))
        ff.write('Clustering result,' + '/'.join(c_num) + '\n')
        print('Silhouette score: ' + str(ret[3]))
        ff.write('Silhouette score,' + str(ret[3]) + '\n')
        ff.close()
    print('Cluster result is saved in {}'.format(outpath))


def difference(inpath, outpath):
    f = open(outpath + '/covas.txt', 'r')
    cova = [line.strip() for line in f.readlines()]
    f.close()
    f = open(outpath + '/regions.txt', 'r')
    region = [line.strip() for line in f.readlines()]
    f.close()
    ctrl_path = os.path.normpath(os.path.join(inpath, 'controls.csv'))
    pati_path = os.path.normpath(os.path.join(inpath, 'patients.csv'))
    ctrl = read_dataset(filepath=ctrl_path, tp='ctrl', cova=cova, region=region)
    pati = read_dataset(filepath=pati_path, tp='pati', cova=cova, region=region)
    PCCh = PCC(covas=ctrl[0], regions=ctrl[1], group=ctrl[2])
    PCCp = PCC(covas=pati[1], regions=pati[2], group=pati[3])
    dif_group = (PCCp - PCCh) / (PCCp + PCCh)
    n = 0
    Z = np.zeros(dif_group.shape)
    for root, dirs, files in os.walk(outpath, topdown=False):
        if len(files) == 2:
            z_path = os.path.join(root, [i for i in files if 'Z.csv' in i][0])
            Z += pd.read_csv(z_path, index_col=0).values
            n += 1
    if n > 1:
        Z /= (n - 1)
    dif_ind_mean = Z
    corr = sps.pearsonr(dif_group.flatten(), dif_ind_mean.flatten())
    print('The Pearson correlation between dif_group and dif_individual_mean is %.4f, p-value is %.4f' % (
        corr[0], corr[1]))


def getConnection(input_dir, fdr=False):
    assert isinstance(input_dir, str), 'input dir must be a string.'
    inputdir = input_dir
    if input_dir[-1] in ['/', '\\']:
        inputdir = input_dir[:-1]
    dirlist = os.listdir(inputdir)
    assert 'regions.txt' in dirlist, 'regions.txt not found.'
    f_re = open(inputdir + '/regions.txt', 'r')
    regions = [line.strip() for line in f_re.readlines()]
    pati = []
    for f in dirlist:
        if os.path.isdir(inputdir + '/' + f):
            pati.append(f)
    significant = None
    for p in pati:
        Z = read_matrix(inputdir + '/' + p + '/' + p + '_Z.csv', tp='z')
        if significant is None:
            significant = np.zeros(Z.shape)
        _P, correct_P = P(Z)
        signi_conn_index = np.argwhere(_P < 0.05)
        if fdr:
            signi_conn_index = np.argwhere(correct_P < 0.05)
        if signi_conn_index.shape[0] > 0:
            rows, cols = zip(*signi_conn_index)
            significant[rows, cols] = significant[rows, cols] + 1
    sorted_edges = draw_signifcant(inputdir + '/' + inputdir.strip().split('/')[-1] + '.jpg', significant, regions,
                                   False)
    sg_num = []
    for se in sorted_edges:
        sg_num.append(str(int(se[0])) + '/' + str(se[1][0]))
    print('Significant_count/Edge_num:')
    print(sg_num)
    select_num = int(input('Please input number of selected edges: '))
    selected_edges = getTopLocs(sorted_edges, select_num)
    print('Selected {} edges'.format(len(selected_edges)))

    row, col = zip(*selected_edges)
    df = pd.DataFrame(columns=['Subject'] + [regions[con[0]] + '--' + regions[con[1]] for con in selected_edges])
    for p in pati:
        df.loc[len(df.index)] = [p] + list(pd.read_csv(inputdir + '/' + p + '/' + p + '_Z.csv', index_col=0).values[
                                               row, col].flatten())
    df.to_csv(inputdir + '/sig_' + str(len(selected_edges)) + '.csv', index=False)


def SCN(inpath, outpath, cova=None, region=None, n_permutations=1000):
    outPath = outpath
    if outpath[-1] in ['/', '\\']:
        outPath = outpath[:-1]
    if not os.path.exists(outPath) or os.path.isfile(outPath):
        os.makedirs(outPath)
    ctrl_path = os.path.normpath(os.path.join(inpath, 'controls.csv'))
    pati_path = os.path.normpath(os.path.join(inpath, 'patients.csv'))
    print('Controls are in {}'.format(ctrl_path))
    print('Patients are in {}'.format(pati_path))
    ctrl = read_dataset(filepath=ctrl_path, tp='ctrl', cova=cova, region=region)
    pati = read_dataset(filepath=pati_path, tp='pati', cova=cova, region=region)

    df = pd.DataFrame(columns=ctrl[1], index=ctrl[1])
    print('calculating real difference ...')

    PCCn = PCC(covas=ctrl[0], regions=ctrl[1], group=ctrl[2])
    PCCn_p = PCC(covas=pati[1], regions=pati[2], group=pati[3])

    # 设置seaborn样式
    sns.set(style='white')
    # colors = ['darkblue', 'blue', 'green', 'darkorange', 'gold']  # 蓝、绿、橙
    # cmap = mcolors.LinearSegmentedColormap.from_list('cmap', colors)

    for t, r in [('rHC', PCCn), ('rMDD', PCCn_p)]:
        # 创建热图
        fig, ax = plt.subplots(figsize=(14, 14), dpi=200)
        hmap = sns.heatmap(r, cmap="viridis", ax=ax,
                           xticklabels=ctrl[1],
                           yticklabels=ctrl[1],
                           cbar_kws={"shrink": .75},
                           annot=False, square=True,
                           vmin=-1, vmax=1)

        cbar = hmap.collections[0].colorbar  # 显示colorbar
        cbar.ax.tick_params(labelsize=20)  # 设置colorbar刻度字体大小。

        # 旋转x轴标签
        ax.set_xticklabels(ax.get_xticklabels(), rotation=-45, ha='left')

        # 添加标题
        plt.title(f'{t}')

        plt.tight_layout()

        # 显示热图
        plt.savefig(outPath + f'/{t}.jpg')

    diff_real = PCCn_p - PCCn

    print('real_diff done.')
    n = diff_real.shape[0]

    g1g2 = pd.concat([ctrl[2], pati[3]])

    # 计算随机差异值
    print('calculating permutate difference ...')
    D_permuted = np.zeros((n_permutations, n, n))
    for i in trange(n_permutations, ncols=100):
        randlabel = list(np.random.permutation(g1g2.shape[0]))
        g1_per = g1g2.iloc[randlabel[:ctrl[2].shape[0]], :]
        g2_per = g1g2.iloc[randlabel[ctrl[2].shape[0]:], :]
        PCCn_per = PCC(covas=ctrl[0], regions=ctrl[1], group=g1_per)
        PCCn_p_per = PCC(covas=ctrl[0], regions=ctrl[1], group=g2_per)
        D_permuted[i] = PCCn_p_per - PCCn_per
    print('perm_diff done.')
    # 计算两组之间的边差异
    D_obs = np.abs(np.arctanh(PCCn) - np.arctanh(PCCn_p))

    # 计算 z 值矩阵
    z_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            z = (D_obs[i, j] - np.mean(D_permuted[:, i, j])) / np.std(D_permuted[:, i, j])
            z_matrix[i, j] = z
            z_matrix[j, i] = z

    # 计算 FDR 校正的 p 值矩阵
    p_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            if diff_real[i, j] > 0:
                p = ((D_permuted[:, i, j].flatten() > diff_real[i, j]).astype(np.int_).sum() + 1) / (n_permutations + 1)
            else:
                p = ((D_permuted[:, i, j].flatten() < diff_real[i, j]).astype(np.int_).sum() + 1) / (n_permutations + 1)
            p_matrix[i, j] = p
            p_matrix[j, i] = p
    fdr_p_matrix = smsm.multipletests(p_matrix[np.triu_indices(n, 1)], method='fdr_bh')[1]
    fdr_p = np.zeros((n, n))
    fdr_p[np.triu_indices(n, 1)] = fdr_p_matrix
    fdr_p[np.tril_indices(n, -1)] = fdr_p.T[np.tril_indices(n, -1)]
    fdr_p[np.diag_indices(n)] = 1.0

    df.iloc[:, :] = z_matrix.T
    df.to_csv(outPath + '/SCN_Z.csv')
    df.iloc[:, :] = fdr_p.T
    df.to_csv(outPath + '/SCN_P_FDR.csv')
    print('SCN done.')
