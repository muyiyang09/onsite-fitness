package com.onsitefitness.dto;

import lombok.Data;

import java.io.Serializable;

@Data
public class ServiceCompleteDTO implements Serializable {

    private Long id;

    //教练id
    private Long coachId;

    //训练记录(JSON)
    private String trainRecord;

    //体测数据(JSON)
    private String bodyData;
}
