package com.onsitefitness.service.impl;

import com.onsitefitness.entity.DispatchPool;
import com.onsitefitness.mapper.DispatchPoolMapper;
import com.onsitefitness.service.DispatchPoolService;
import com.onsitefitness.vo.DispatchPoolVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@Slf4j
public class DispatchPoolServiceImpl implements DispatchPoolService {

    @Autowired
    private DispatchPoolMapper dispatchPoolMapper;

    /**
     * 派单池可抢列表(教练端按城市)
     */
    @Override
    public List<DispatchPoolVO> listSeizable(String cityCode) {
        return dispatchPoolMapper.listSeizableByCityCode(cityCode, DispatchPool.STATUS_PENDING);
    }

    /**
     * 管理端：查询全部派单池记录（可按状态/城市筛选）
     */
    @Override
    public List<DispatchPoolVO> listAllForAdmin(Integer status, String cityCode) {
        return dispatchPoolMapper.listAllForAdmin(status, cityCode);
    }
}
