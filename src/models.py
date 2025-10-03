from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from src.database import Base

class Sentence(Base):
    __tablename__ = 'sentences'
    id = Column(Integer, primary_key=True, index=True)
    elan_sentence = Column(Text, nullable=False)
    updated_sentence = Column(Text, nullable=False)
    translation = Column(Text, nullable=False)
    elan_gloss = Column(Text, nullable=True) # Can be empty

    words = relationship("SentenceWord", back_populates="sentence", cascade="all, delete-orphan")

class Wordform(Base):
    __tablename__ = 'wordforms'
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, unique=True, index=True, nullable=False)

class Lexeme(Base):
    __tablename__ = 'lexemes'
    id = Column(Integer, primary_key=True, index=True)
    root = Column(Text, nullable=False)
    part_of_speech = Column(String, nullable=False)
    gloss = Column(Text, nullable=True)
    lexical_info = Column(JSONB, nullable=True)

class Parse(Base):
    __tablename__ = 'parses'
    id = Column(Integer, primary_key=True, index=True)
    updated_form = Column(Text, nullable=False)
    source = Column(String, default="FST")
    comment = Column(Text, nullable=True)

    wordform_id = Column(Integer, ForeignKey('wordforms.id'), nullable=False)
    lexeme_id = Column(Integer, ForeignKey('lexemes.id'), nullable=False)

    analysis = Column(JSONB, nullable=False)

    wordform = relationship("Wordform")
    lexeme = relationship("Lexeme")



class SentenceWord(Base):
    """
    This is the association table that links words to sentences in a specific order.
    It represents a single word in a specific context.
    """
    __tablename__ = 'sentence_words'
    id = Column(Integer, primary_key=True, index=True)
    position = Column(Integer, nullable=False)
    checked_by_pi = Column(Boolean, default=False)

    sentence_id = Column(Integer, ForeignKey('sentences.id'), nullable=False)
    wordform_id = Column(Integer, ForeignKey('wordforms.id'), nullable=False)
    
    chosen_parse_id = Column(Integer, ForeignKey('parses.id'), nullable=True)

    sentence = relationship("Sentence", back_populates="words")
    wordform = relationship("Wordform")
    chosen_parse = relationship("Parse")