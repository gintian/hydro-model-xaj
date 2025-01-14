import os
import numpy as np
import pandas as pd
import pathlib
import spotpy
from pathlib import Path
import sys


sys.path.append(os.path.dirname(Path(os.path.abspath(__file__)).parent.parent))
import definitions
from hydromodel.utils import hydro_utils
from hydromodel.models.model_config import MODEL_PARAM_DICT
from hydromodel.models.xaj import xaj


def read_save_sceua_calibrated_params(basin_id, save_dir, sceua_calibrated_file_name):
    """
    read the parameters' file generated by spotpy SCE-UA when finishing calibration

    We also save the parameters of the best model run to a file

    Parameters
    ----------
    basin_id
        id of a basin
    save_dir
        the directory where we save params
    sceua_calibrated_file_name
        the parameters' file generated by spotpy SCE-UA when finishing calibration

    Returns
    -------

    """
    results = spotpy.analyser.load_csv_results(sceua_calibrated_file_name)
    bestindex, bestobjf = spotpy.analyser.get_minlikeindex(results)
    best_model_run = results[bestindex]
    fields = [word for word in best_model_run.dtype.names if word.startswith("par")]
    best_calibrate_params = pd.DataFrame(list(best_model_run[fields]))
    save_file = os.path.join(save_dir, basin_id + "_calibrate_params.txt")
    best_calibrate_params.to_csv(save_file, sep=",", index=False, header=True)
    return np.array(best_calibrate_params).reshape(1, -1)


def summarize_parameters(result_dir, model_info: dict):
    """
    output parameters of all basins to one file

    Parameters
    ----------
    result_dir
        the directory where we save results
    model_name
        the name of the model

    Returns
    -------

    """
    path = pathlib.Path(result_dir)
    all_basins_dirs = [file for file in path.iterdir() if file.is_dir()]
    params = []
    basin_ids = []
    for basin_dir in all_basins_dirs:
        basin_id = basin_dir.stem
        columns = MODEL_PARAM_DICT[model_info["name"]]["param_name"]
        params_txt = pd.read_csv(
            os.path.join(basin_dir, basin_id + "_calibrate_params.txt")
        )
        params_df = pd.DataFrame(params_txt.values.T, columns=columns)
        params.append(params_df)
        basin_ids.append(basin_id)
    params_dfs = pd.concat(params, axis=0)
    params_dfs.index = basin_ids
    print(params_dfs)
    params_dfs_ = params_dfs.transpose()
    params_csv_file = os.path.join(result_dir, "basins_params.csv")
    params_dfs_.to_csv(params_csv_file, sep=",", index=True, header=True)


def renormalize_params(result_dir, model_info: dict):
    path = pathlib.Path(result_dir)
    all_basins_files = [file for file in path.iterdir() if file.is_dir()]
    renormalization_params = []
    basin_ids = []
    for basin_dir in all_basins_files:
        basin_id = basin_dir.stem
        basin_ids.append(basin_id)
        params = np.loadtxt(
            os.path.join(basin_dir, basin_id + "_calibrate_params.txt")
        )[1:].reshape(1, -1)
        param_ranges = MODEL_PARAM_DICT[model_info["name"]]["param_range"]
        xaj_params = [
            (value[1] - value[0]) * params[:, i] + value[0]
            for i, (key, value) in enumerate(param_ranges.items())
        ]
        xaj_params_ = np.array([x for j in xaj_params for x in j])
        params_df = pd.DataFrame(xaj_params_.T)
        renormalization_params.append(params_df)
    renormalization_params_dfs = pd.concat(renormalization_params, axis=1)
    renormalization_params_dfs.index = MODEL_PARAM_DICT[model_info["name"]][
        "param_name"
    ]
    renormalization_params_dfs.columns = basin_ids
    print(renormalization_params_dfs)
    params_csv_file = os.path.join(result_dir, "basins_renormalization_params.csv")
    renormalization_params_dfs.to_csv(params_csv_file, sep=",", index=True, header=True)


def summarize_metrics(result_dir, model_info: dict):
    """
    output all results' metrics of all basins to one file

    Parameters
    ----------
    result_dir
        the directory where we save results

    Returns
    -------

    """
    path = pathlib.Path(result_dir)
    all_basins_files = [file for file in path.iterdir() if file.is_dir()]
    train_metrics = {}
    test_metrics = {}
    count = 0
    basin_ids = []
    for basin_dir in all_basins_files:
        basin_id = basin_dir.stem
        basin_ids.append(basin_id)
        train_metric_file = os.path.join(basin_dir, "train_metrics.json")
        test_metric_file = os.path.join(basin_dir, "test_metrics.json")
        train_metric = hydro_utils.unserialize_json(train_metric_file)
        test_metric = hydro_utils.unserialize_json(test_metric_file)

        for key, value in train_metric.items():
            if count == 0:
                train_metrics[key] = value
            else:
                train_metrics[key] = train_metrics[key] + value
        for key, value in test_metric.items():
            if count == 0:
                test_metrics[key] = value
            else:
                test_metrics[key] = test_metrics[key] + value
        count = count + 1
    metric_dfs_train = pd.DataFrame(train_metrics, index=basin_ids).transpose()
    metric_dfs_test = pd.DataFrame(test_metrics, index=basin_ids).transpose()
    metric_file_train = os.path.join(result_dir, "basins_metrics_train.csv")
    metric_file_test = os.path.join(result_dir, "basins_metrics_test.csv")
    metric_dfs_train.to_csv(metric_file_train, sep=",", index=True, header=True)
    metric_dfs_test.to_csv(metric_file_test, sep=",", index=True, header=True)


def save_streamflow(result_dir, model_info: dict, fold: int):
    path = pathlib.Path(result_dir)
    all_basins_files = [file for file in path.iterdir() if file.is_dir()]
    streamflow_test = []
    streamflow_train = []
    basin_ids = []
    for basin_dir in all_basins_files:
        basin_id = basin_dir.stem
        basin_ids.append(basin_id)
        streamflow_df_test = pd.read_csv(
            os.path.join(
                basin_dir, "test_qsim_" + model_info["name"] + "_" + basin_id + ".csv"
            ),
            header=None,
        )
        streamflow_df_train = pd.read_csv(
            os.path.join(
                basin_dir, "train_qsim_" + model_info["name"] + "_" + basin_id + ".csv"
            ),
            header=None,
        )
        streamflow_test.append(streamflow_df_test)
        streamflow_train.append(streamflow_df_train)
    streamflow_dfs_test = pd.concat(streamflow_test, axis=1)
    streamflow_dfs_train = pd.concat(streamflow_train, axis=1)
    streamflow_dfs_test.columns = basin_ids
    streamflow_dfs_train.columns = basin_ids
    test_info_file = path.parent.joinpath("data_info_fold" + str(fold) + "_test.json")
    test_info = hydro_utils.unserialize_json(test_info_file)
    date_test = test_info["time"][-streamflow_dfs_test.shape[0] :]
    streamflow_dfs_test.index = date_test
    train_info_file = path.parent.joinpath("data_info_fold" + str(fold) + "_train.json")
    train_info = hydro_utils.unserialize_json(train_info_file)
    date_train = train_info["time"][-streamflow_dfs_train.shape[0] :]
    streamflow_dfs_train.index = date_train
    eva_csv_file_test = os.path.join(result_dir, "basin_qsim_test.csv")
    eva_csv_file_train = os.path.join(result_dir, "basin_qsim_train.csv")
    streamflow_dfs_test.to_csv(eva_csv_file_test)
    streamflow_dfs_train.to_csv(eva_csv_file_train)


def read_and_save_et_ouputs(result_dir, fold: int):
    prameter_file = os.path.join(result_dir, "basins_params.csv")
    param_values = pd.read_csv(prameter_file, index_col=0)
    basins_id = param_values.columns.values
    args_file = os.path.join(result_dir, "args.json")
    args = hydro_utils.unserialize_json(args_file)
    warmup_length = args["warmup_length"]
    model_func_param = args["model"]
    exp_dir = pathlib.Path(result_dir).parent
    data_info_train = hydro_utils.unserialize_json(
        exp_dir.joinpath("data_info_fold" + str(fold) + "_train.json")
    )
    data_info_test = hydro_utils.unserialize_json(
        exp_dir.joinpath("data_info_fold" + str(fold) + "_test.json")
    )
    train_period = data_info_train["time"]
    test_period = data_info_test["time"]
    train_np_file = os.path.join(
        exp_dir, "basins_lump_p_pe_q_fold" + str(fold) + "_train.npy"
    )
    test_np_file = os.path.join(
        exp_dir, "basins_lump_p_pe_q_fold" + str(fold) + "_test.npy"
    )
    train_data = np.load(train_np_file)
    test_data = np.load(test_np_file)
    es_test = []
    es_train = []
    for i in range(len(basins_id)):
        _, e_train = xaj(
            train_data[:, :, 0:2],
            param_values[basins_id[i]].values.reshape(1, -1),
            warmup_length=warmup_length,
            **model_func_param
        )
        _, e_test = xaj(
            test_data[:, :, 0:2],
            param_values[basins_id[i]].values.reshape(1, -1),
            warmup_length=warmup_length,
            **model_func_param
        )
        es_train.append(e_train.flatten())
        es_test.append(e_test.flatten())
    df_e_train = pd.DataFrame(
        np.array(es_train).T, columns=basins_id, index=train_period[warmup_length:]
    )
    df_e_test = pd.DataFrame(
        np.array(es_test).T, columns=basins_id, index=test_period[warmup_length:]
    )
    etsim_train_save_path = os.path.join(result_dir, "basin_etsim_train.csv")
    etsim_test_save_path = os.path.join(result_dir, "basin_etsim_test.csv")
    df_e_train.to_csv(etsim_train_save_path)
    df_e_test.to_csv(etsim_test_save_path)


if __name__ == "__main__":
    one_model_one_hyperparam_setting_dir = os.path.join(
        definitions.ROOT_DIR,
        "hydromodel",
        "example",
        "exp61561",
        "Dec08_11-38-48_LAPTOP-DNQOPPMS_fold1_HFsourcesrep1000ngs1000",
    )
    read_and_save_et_ouputs(one_model_one_hyperparam_setting_dir, fold=1)
    # summarize_parameters(one_model_one_hyperparam_setting_dir, {"name": "xaj_mz"})
    # renormalize_params(one_model_one_hyperparam_setting_dir, {"name":"xaj_mz"})
    # summarize_metrics(one_model_one_hyperparam_setting_dir,{"name":"xaj_mz"})
    # save_streamflow(one_model_one_hyperparam_setting_dir,{"name":"xaj_mz"})
