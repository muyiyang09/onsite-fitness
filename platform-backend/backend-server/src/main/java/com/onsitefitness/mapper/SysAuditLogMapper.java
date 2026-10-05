package com.onsitefitness.mapper;

import com.onsitefitness.entity.SysAuditLog;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface SysAuditLogMapper {

    /**
     * 写入一条业务审计日志。
     */
    @Insert("insert into sys_audit_log (user_id, type, biz_id, detail, json_extra, created_at) " +
            "values (#{userId}, #{type}, #{bizId}, #{detail}, #{jsonExtra}, #{createdAt})")
    void insert(SysAuditLog auditLog);
}
