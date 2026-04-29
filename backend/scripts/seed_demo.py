import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.ai_config import AIConfig
from app.models.class_ import Class
from app.models.prompt_template import PromptTemplate
from app.models.user import User
from app.utils.security import hash_password
import json


async def seed():
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Demo data already exists, skipping.")
            return

        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            real_name="系统管理员",
            role="admin",
            must_change_password=True,
        )
        db.add(admin)
        await db.flush()

        teacher = User(
            username="teacher1",
            password_hash=hash_password("teacher123"),
            real_name="王老师",
            role="teacher",
            must_change_password=True,
        )
        db.add(teacher)
        await db.flush()

        cls = Class(
            name="计算机网络1班",
            semester="2025-2026-2",
            teacher_id=teacher.id,
        )
        db.add(cls)
        await db.flush()

        student = User(
            username="student1",
            password_hash=hash_password("student123"),
            real_name="张三",
            role="student",
            primary_class_id=cls.id,
            must_change_password=True,
        )
        db.add(student)
        await db.flush()

        # AI Config defaults
        ai_configs = [
            AIConfig(key="model", value="gpt-4o-mini"),
            AIConfig(key="budget_admin", value="500000"),
            AIConfig(key="budget_teacher", value="200000"),
            AIConfig(key="budget_student", value="50000"),
            AIConfig(key="price_input", value="0.15"),
            AIConfig(key="price_output", value="0.60"),
        ]
        for c in ai_configs:
            db.add(c)

        # Default prompt templates
        templates = [
            PromptTemplate(
                name="task_description",
                description="生成任务描述",
                template_text=(
                    "请为「{course_name}」课程生成一个关于「{topic}」的实训任务说明草稿，要求包含以下部分：\n\n"
                    "## 任务背景\n简要说明该任务的背景和实际意义。\n\n"
                    "## 任务目标\n列出 3-5 个具体、可衡量的学习目标。\n\n"
                    "## 实施步骤\n分步骤说明学生需要完成的工作，每一步包含具体操作指导。\n\n"
                    "## 提交要求\n说明需要提交的内容、格式和命名规范。\n\n"
                    "## 评分要点\n列出评分维度（如完成度、代码质量、文档规范性等）和权重建议。\n\n"
                    "请使用{language}撰写，确保内容清晰、可操作。只输出任务说明正文，不要输出额外解释。"
                ),
                variables=json.dumps(["course_name", "topic", "language"]),
            ),
            PromptTemplate(
                name="student_qa",
                description="学生任务问答",
                template_text=(
                    "你是课程助教，根据以下任务信息回答学生的问题。\n\n"
                    "## 可用上下文\n"
                    "课程：{course_name}\n"
                    "任务：{task_title}\n"
                    "描述：{task_description}\n"
                    "要求：{task_requirements}\n\n"
                    "## 严格规则\n"
                    "1. 只使用上方提供的上下文信息回答问题，不要使用外部知识\n"
                    "2. 如果上下文信息不足以回答问题，明确回复「根据当前任务信息无法回答这个问题，建议咨询任课教师。」\n"
                    "3. 不要编造、推测或补充任何上下文中未提及的内容\n"
                    "4. 用简洁清晰的中文回答\n\n"
                    "学生问题：{question}"
                ),
                variables=json.dumps(["task_title", "task_description", "task_requirements", "course_name", "question"]),
            ),
            PromptTemplate(
                name="training_summary",
                description="生成实训总结",
                template_text=(
                    "你是教学助教，请根据学生的提交记录生成一份实训总结初稿。\n\n"
                    "## 学生提交记录\n"
                    "{submissions_context}\n\n"
                    "## 严格规则\n"
                    "1. 只根据上方提供的提交记录生成总结，不要编造不存在的任务或成果\n"
                    "2. 总结结构：学习概述、主要收获、不足与改进建议、下一步学习计划\n"
                    "3. 如果提交记录很少，明确指出数据不足\n"
                    "4. 用简洁清晰的中文撰写，长度 300-800 字\n"
                    "5. 这是初稿，学生可能会修改，不要加标题或格式标记\n"
                ),
                variables=json.dumps(["submissions_context"]),
            ),
        ]
        for t in templates:
            db.add(t)

        await db.flush()

        await db.commit()
        print(f"Created: admin({admin.id}), teacher1({teacher.id}), class({cls.id}), student1({student.id})")


if __name__ == "__main__":
    asyncio.run(seed())
