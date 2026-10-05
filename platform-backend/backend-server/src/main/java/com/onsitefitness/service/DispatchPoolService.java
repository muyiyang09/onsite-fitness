package com.onsitefitness.service;

import com.onsitefitness.vo.DispatchPoolVO;

import java.util.List;

/**
 * 派单池服务
 */
public interface DispatchPoolService {

    /**
     * 派单池可抢列表(教练端按城市)
     * @param cityCode 教练服务城市编码
     */
    List<DispatchPoolVO> listSeizable(String cityCode);

    /**
     * 管理端：查询全部派单池记录（可按状态/城市筛选）
     */
    List<DispatchPoolVO> listAllForAdmin(Integer status, String cityCode);
}
